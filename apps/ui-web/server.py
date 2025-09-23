import os
import asyncio
import logging
from typing import Set
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
import asyncio_mqtt as mqtt
import orjson
from urllib.parse import urlparse

MQTT_URL = os.getenv("MQTT_URL", "mqtt://tars:pass@127.0.0.1:1883")
# STT topics
PARTIAL_TOPIC = os.getenv("UI_PARTIAL_TOPIC", "stt/partial")
FINAL_TOPIC = os.getenv("UI_FINAL_TOPIC", "stt/final")
FFT_TOPIC = os.getenv("UI_AUDIO_TOPIC", "stt/audio_fft")
# TTS topics
TTS_TOPIC = os.getenv("UI_TTS_TOPIC", "tts/status")
TTS_SAY_TOPIC = os.getenv("UI_TTS_SAY_TOPIC", "tts/say")
# LLM topics
LLM_STREAM_TOPIC = os.getenv("UI_LLM_STREAM_TOPIC", "llm/stream")
LLM_RESPONSE_TOPIC = os.getenv("UI_LLM_RESPONSE_TOPIC", "llm/response")

app = FastAPI()
logger = logging.getLogger("ui-web")
logging.basicConfig(level=os.getenv("LOG_LEVEL", "INFO"))

# Serve static index.html from ./static
app.mount("/static", StaticFiles(directory="static"), name="static")

class ConnectionManager:
    def __init__(self):
        self.active: Set[WebSocket] = set()
        self._lock = asyncio.Lock()

    async def connect(self, ws: WebSocket):
        await ws.accept()
        async with self._lock:
            self.active.add(ws)

    async def disconnect(self, ws: WebSocket):
        async with self._lock:
            self.active.discard(ws)

    async def broadcast(self, message: dict):
        data = orjson.dumps(message).decode()
        to_remove = []
        async with self._lock:
            for ws in list(self.active):
                try:
                    await ws.send_text(data)
                except Exception:
                    to_remove.append(ws)
            for ws in to_remove:
                self.active.discard(ws)

manager = ConnectionManager()

def parse_mqtt(url: str):
    u = urlparse(url)
    return u.hostname or "127.0.0.1", u.port or 1883, u.username, u.password

async def mqtt_bridge_task():
    host, port, username, password = parse_mqtt(MQTT_URL)
    topics = [
        PARTIAL_TOPIC,
        FINAL_TOPIC,
        FFT_TOPIC,
        TTS_TOPIC,
        TTS_SAY_TOPIC,
        LLM_STREAM_TOPIC,
        LLM_RESPONSE_TOPIC,
    ]
    while True:
        try:
            logger.info(f"Connecting to MQTT {host}:{port}")
            async with mqtt.Client(hostname=host, port=port, username=username, password=password) as client:
                logger.info("Connected to MQTT, subscribing topics")
                async with client.messages() as messages:
                    for t in topics:
                        await client.subscribe(t)
                        logger.info(f"Subscribed to {t}")
                    async for msg in messages:
                        try:
                            payload = orjson.loads(msg.payload)
                        except Exception:
                            payload = {"raw": (msg.payload.decode(errors="ignore") if isinstance(msg.payload, (bytes, bytearray)) else str(msg.payload))}
                        # Normalize topic to a string for browser clients
                        topic_obj = getattr(msg, "topic", None)
                        if isinstance(topic_obj, (bytes, bytearray)):
                            topic_str = topic_obj.decode("utf-8", "ignore")
                        elif isinstance(topic_obj, str):
                            topic_str = topic_obj
                        else:
                            topic_str = getattr(topic_obj, "value", str(topic_obj))
                        logger.debug(f"Forwarding {topic_str}")
                        await manager.broadcast({"topic": topic_str, "payload": payload})
        except Exception as e:
            logger.error(f"MQTT bridge error: {e}")
            await asyncio.sleep(1.0)

@app.on_event("startup")
async def on_start():
    asyncio.create_task(mqtt_bridge_task())

@app.get("/")
async def index():
    try:
        with open(os.path.join("static", "index.html"), "r", encoding="utf-8") as f:
            return HTMLResponse(f.read())
    except Exception:
        return HTMLResponse("<h1>TARS Web UI</h1>")

@app.websocket("/ws")
async def ws_endpoint(ws: WebSocket):
    await manager.connect(ws)
    try:
        while True:
            # Keepalive: accept pings/messages but we don't expect client messages
            await ws.receive_text()
    except WebSocketDisconnect:
        pass
    finally:
        await manager.disconnect(ws)