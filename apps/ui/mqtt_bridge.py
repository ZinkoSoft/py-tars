"""MQTT bridge utilities for the pygame UI."""
from __future__ import annotations

import logging
import queue
import threading
from typing import Mapping

import orjson
import paho.mqtt.client as mqtt

logger = logging.getLogger("tars.ui.mqtt")


class MqttBridge:
    """Subscribe to MQTT topics and forward decoded messages into a queue."""

    def __init__(
        self,
        event_queue: queue.Queue,
        *,
        host: str,
        port: int,
        topics: Mapping[str, str | None],
        username: str | None = None,
        password: str | None = None,
        subscribe_audio: bool = True,
    ) -> None:
        self.client = mqtt.Client(client_id="tars-ui")
        if username and password:
            self.client.username_pw_set(username, password)
        self.q = event_queue
        self.host = host
        self.port = port
        self.partial_topic = topics.get("partial")
        self.final_topic = topics.get("final")
        self.tts_topic = topics.get("tts")
        self.llm_response_topic = topics.get("llm_response")
        self.audio_topic = topics.get("audio")
        self._subscribe_audio = subscribe_audio and bool(self.audio_topic)
        self.client.on_message = self._on_message
        self._thread: threading.Thread | None = None

    def _on_message(self, client, userdata, msg):  # pragma: no cover - MQTT callback
        try:
            payload = orjson.loads(msg.payload)
        except Exception:
            payload = {}
        try:
            self.q.put_nowait((msg.topic, payload))
        except queue.Full:
            logger.debug("UI event queue full; dropping MQTT message from %s", msg.topic)

    def start(self) -> None:
        self.client.connect(self.host, self.port, 60)
        topics = []
        if self.partial_topic:
            topics.append((self.partial_topic, 0))
        if self.final_topic:
            topics.append((self.final_topic, 0))
        if self.tts_topic:
            topics.append((self.tts_topic, 0))
        if self.llm_response_topic:
            topics.append((self.llm_response_topic, 0))
        if self._subscribe_audio and self.audio_topic:
            topics.append((self.audio_topic, 0))
        logger.info(f"MQTT Bridge subscribing to topics: {topics}")
        if topics:
            self.client.subscribe(topics)
        self._thread = threading.Thread(target=self.client.loop_forever, daemon=True)
        self._thread.start()

    def poll(self):
        try:
            return self.q.get_nowait()
        except queue.Empty:
            return None, None

    def stop(self) -> None:
        try:
            self.client.disconnect()
        except Exception:
            pass
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=1.0)

