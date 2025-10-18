import os
import asyncio
import logging
from pathlib import Path
from typing import Set, Any, Dict
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.responses import HTMLResponse, JSONResponse, FileResponse
from fastapi.staticfiles import StaticFiles
from tars.adapters.mqtt_client import MQTTClient  # type: ignore[import]
import orjson

from ui_web.config import Config

# Load configuration
config = Config.from_env()

app = FastAPI()
logger = logging.getLogger("ui-web")
logging.basicConfig(level=config.log_level)

# Determine if we're serving the Vue.js built frontend or legacy static HTML
frontend_dist = Path(__file__).parent.parent.parent / "frontend" / "dist"
static_dir = Path(__file__).parent.parent.parent / "static"

if frontend_dist.exists() and (frontend_dist / "index.html").exists():
    # Serve Vue.js built frontend (production)
    logger.info(f"Serving Vue.js frontend from {frontend_dist}")
    app.mount("/assets", StaticFiles(directory=str(frontend_dist / "assets")), name="assets")
    FRONTEND_MODE = "vue"
    INDEX_HTML_PATH = frontend_dist / "index.html"
elif static_dir.exists():
    # Fallback to legacy static HTML
    logger.info(f"Serving legacy static HTML from {static_dir}")
    app.mount("/static", StaticFiles(directory=str(static_dir)), name="static")
    FRONTEND_MODE = "legacy"
    INDEX_HTML_PATH = static_dir / "index.html"
else:
    logger.warning("No frontend found - serving minimal HTML")
    FRONTEND_MODE = "none"
    INDEX_HTML_PATH = None


class ConnectionManager:
    def __init__(self) -> None:
        self.active: Set[WebSocket] = set()
        self._lock = asyncio.Lock()
        self._health_cache: Dict[str, Dict[str, Any]] = {}  # Cache retained health messages

    async def connect(self, ws: WebSocket) -> None:
        await ws.accept()
        async with self._lock:
            self.active.add(ws)
            # Send cached health messages to new connection
            for topic, payload in self._health_cache.items():
                try:
                    message = {"topic": topic, "payload": payload}
                    data = orjson.dumps(message).decode()
                    await ws.send_text(data)
                except Exception as e:
                    logger.warning(f"Failed to send cached health to new connection: {e}")

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

    async def cache_health(self, topic: str, payload: Dict[str, Any]) -> None:
        """Cache health messages for new connections (mimics MQTT retained messages)"""
        async with self._lock:
            self._health_cache[topic] = payload


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
    
    # Create message handler factory for each topic (closure captures topic name)
    def make_handler(topic: str):
        async def handler(payload: bytes) -> None:
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

            # Cache and log health messages (mimics MQTT retained message behavior)
            if topic.startswith("system/health/"):
                logger.info("Health message: %s -> %s", topic, payload_data)
                await manager.cache_health(topic, payload_data)

            logger.debug(f"Forwarding {topic}")
            await manager.broadcast({"topic": topic, "payload": payload_data})
        
        return handler

    # Use centralized MQTT client with reconnection support
    while True:
        mqtt_client = None
        try:
            logger.info(f"Connecting to MQTT {config.mqtt_host}:{config.mqtt_port}")
            mqtt_url = config.mqtt_url
            mqtt_client = MQTTClient(mqtt_url, "ui-web", enable_health=False)
            await mqtt_client.connect()
            
            logger.info("Connected to MQTT, subscribing topics")
            for topic in topics:
                await mqtt_client.subscribe(topic, make_handler(topic))
                logger.info(f"Subscribed to {topic}")
            
            # Keep connection alive and process messages
            # MQTTClient handles reconnection internally
            while True:
                await asyncio.sleep(1.0)
                
        except Exception as e:
            logger.error("MQTT bridge error: %s", e)
            if mqtt_client:
                try:
                    await mqtt_client.shutdown()
                except Exception:
                    pass
            await asyncio.sleep(5.0)  # Wait before reconnecting


@app.on_event("startup")
async def on_start() -> None:
    asyncio.create_task(mqtt_bridge_task())


@app.get("/")
async def index() -> HTMLResponse:
    """Serve the frontend index.html (Vue.js or legacy)."""
    if INDEX_HTML_PATH and INDEX_HTML_PATH.exists():
        try:
            with open(INDEX_HTML_PATH, "r", encoding="utf-8") as f:
                return HTMLResponse(f.read())
        except Exception as e:
            logger.error(f"Failed to serve index.html: {e}")
            return HTMLResponse("<h1>TARS Web UI - Error loading frontend</h1>", status_code=500)
    else:
        return HTMLResponse("<h1>TARS Web UI - No frontend configured</h1>", status_code=404)


@app.get("/api/memory")
async def api_memory(q: str = "*", k: int = 25) -> JSONResponse:
    """Return the last known memory/results and optionally trigger a fresh query.

    This is a lightweight proxy: it publishes memory/query and returns the
    most recent memory/results snapshot cached by the bridge.
    """
    try:
        # Create temporary MQTT client for one-off publish
        mqtt_url = config.mqtt_url
        temp_client = MQTTClient(mqtt_url, "ui-web-api", enable_health=False)
        await temp_client.connect()
        try:
            await temp_client.publish(config.memory_query_topic, orjson.dumps({"text": q, "top_k": k}))
        finally:
            await temp_client.shutdown()
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

    uvicorn.run(app, host="0.0.0.0", port=config.port, log_level=config.log_level.lower())


if __name__ == "__main__":
    main()
