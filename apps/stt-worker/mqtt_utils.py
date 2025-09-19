import asyncio
import logging
from urllib.parse import urlparse
import asyncio_mqtt as mqtt
import orjson
from typing import Callable, Awaitable, Optional

logger = logging.getLogger("stt-worker.mqtt")

class MQTTClientWrapper:
    def __init__(self, mqtt_url: str, client_id: str = 'tars-stt'):
        self.mqtt_url = mqtt_url
        self.client_id = client_id
        self.client: Optional[mqtt.Client] = None
        self._listener_tasks = []
        self._lock = asyncio.Lock()

    def parse(self):
        u = urlparse(self.mqtt_url)
        return u.hostname or '127.0.0.1', u.port or 1883, u.username, u.password

    async def connect(self):
        host, port, username, password = self.parse()
        logger.info(f"Connecting to MQTT {host}:{port}")
        self.client = mqtt.Client(hostname=host, port=port, username=username, password=password, client_id=self.client_id)
        await self.client.__aenter__()
        logger.info("Connected to MQTT")

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
        async def _runner():
            backoff = 0.5
            while True:
                if not self.client:
                    try:
                        await self.reconnect()
                    except Exception as e:
                        logger.error(f"Reconnect in subscribe_stream failed: {e}")
                        await asyncio.sleep(backoff)
                        backoff = min(backoff * 2, 5)
                        continue
                try:
                    async with self.client.filtered_messages(topic) as messages:
                        await self.client.subscribe(topic)
                        logger.info(f"Subscribed to {topic}")
                        backoff = 0.5
                        async for msg in messages:
                            try:
                                await handler(msg.payload)
                            except Exception as e:
                                logger.error(f"Handler error for topic {topic}: {e}")
                except Exception as e:
                    logger.error(f"Subscription loop error on {topic}: {e}")
                    await asyncio.sleep(backoff)
                    backoff = min(backoff * 2, 5)
                    continue
        task = asyncio.create_task(_runner())
        self._listener_tasks.append(task)
        return task
