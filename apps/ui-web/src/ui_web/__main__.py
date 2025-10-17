import os
import asyncio
import logging
from typing import Set, Any, Dict
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from tars.adapters.mqtt_client import MQTTClient  # type: ignore[import]
import orjson

from ui_web.config import Config

# Load configuration
config = Config.from_env()

app = FastAPI()
logger = logging.getLogger("ui-web")
logging.basicConfig(level=config.log_level)

# Serve static index.html from ./static
app.mount("/static", StaticFiles(directory="static"), name="static")


class ConnectionManager:
    def __init__(self) -> None:
        self.active: Set[WebSocket] = set()
        self._lock = asyncio.Lock()

    async def connect(self, ws: WebSocket) -> None:
        await ws.accept()
        async with self._lock:
            self.active.add(ws)

    async def disconnect(self, ws: WebSocket) -> None:
        async with self._lock:
            self.active.discard(ws)

    async def broadcast(self, message: Dict[str, Any]) -> None:
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

_last_memory_results: Dict[str, Any] = {}


async def mqtt_bridge_task() -> None:
    topics = [
        config.partial_topic,
        config.final_topic,
        config.fft_topic,
        config.tts_topic,
        config.tts_say_topic,
        config.llm_stream_topic,
        config.llm_response_topic,
        config.memory_results_topic,
        config.health_topic,
        # Camera frames now served via MJPEG over HTTP, not MQTT
    ]
    # Use centralized MQTT client with subscription handlers
    mqtt_url = config.mqtt_url
    mqtt_client = MQTTClient(mqtt_url, "ui-web", enable_health=False)
    async def _make_handler(topic: str):
        async def _handler(payload: bytes) -> None:
            try:
                payload_data: Any
                if isinstance(payload, (bytes, bytearray, str)):
                    payload_data = orjson.loads(payload)
                else:
                    payload_data = {"raw": str(payload)}
            except Exception:
                payload_data = {"raw": payload.decode(errors="ignore") if isinstance(payload, (bytes, bytearray)) else str(payload)}

            # Keep a copy of memory/results for REST consumers
            if topic == config.memory_results_topic:
                try:
                    globals()["_last_memory_results"] = payload_data
                except Exception:
                    pass

            # Log health messages for debugging
            if topic.startswith("system/health/"):
                logger.info("Health message: %s -> %s", topic, payload_data)

            await manager.broadcast({"topic": topic, "payload": payload_data})

        return _handler

    while True:
        try:
            logger.info("Connecting to MQTT %s", mqtt_url)
            await mqtt_client.connect()
            # Register subscriptions
            for t in topics:
                handler = await _make_handler(t)
                await mqtt_client.subscribe(t, handler, qos=1)
                logger.info("Subscribed to %s", t)

            # Block until disconnected
            await asyncio.Event().wait()
        except Exception as e:
            logger.error("MQTT bridge error: %s", e)
            try:
                await mqtt_client.shutdown()
            except Exception:
                pass
            await asyncio.sleep(1.0)


@app.on_event("startup")
async def on_start() -> None:
    asyncio.create_task(mqtt_bridge_task())


@app.get("/")
async def index() -> HTMLResponse:
    try:
        with open(os.path.join("static", "index.html"), "r", encoding="utf-8") as f:
            return HTMLResponse(f.read())
    except Exception:
        return HTMLResponse("<h1>TARS Web UI</h1>")


@app.get("/api/memory")
async def api_memory(q: str = "*", k: int = 25) -> JSONResponse:
    """Return the last known memory/results and optionally trigger a fresh query.

    This is a lightweight proxy: it publishes memory/query and returns the
    most recent memory/results snapshot cached by the bridge.
    """
    try:
        async with mqtt.Client(
            hostname=config.mqtt_host,
            port=config.mqtt_port,
            username=config.mqtt_username,
            password=config.mqtt_password,
        ) as client:
            await client.publish(config.memory_query_topic, orjson.dumps({"text": q, "top_k": k}))
    except Exception as e:
        return JSONResponse({"error": str(e)}, status_code=500)
    return JSONResponse(_last_memory_results or {"results": [], "query": q, "k": k})


@app.websocket("/ws")
async def ws_endpoint(ws: WebSocket) -> None:
    await manager.connect(ws)
    try:
        while True:
            # Keepalive: accept pings/messages but we don't expect client messages
            await ws.receive_text()
    except WebSocketDisconnect:
        pass
    finally:
        await manager.disconnect(ws)


def main() -> None:
    """Main entry point for the TARS Web UI."""
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8080, log_level=config.log_level.lower())


if __name__ == "__main__":
    main()
