import os
import asyncio
import logging
from typing import Set, Any, Dict
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
import asyncio_mqtt as mqtt
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
    while True:
        try:
            logger.info(f"Connecting to MQTT {config.mqtt_host}:{config.mqtt_port}")
            async with mqtt.Client(
                hostname=config.mqtt_host,
                port=config.mqtt_port,
                username=config.mqtt_username,
                password=config.mqtt_password,
            ) as client:
                logger.info("Connected to MQTT, subscribing topics")
                async with client.messages() as messages:
                    for t in topics:
                        await client.subscribe(t)
                        logger.info(f"Subscribed to {t}")
                    async for msg in messages:
                        payload_data: Any
                        try:
                            if isinstance(msg.payload, (bytes, bytearray, str)):
                                payload_data = orjson.loads(msg.payload)
                            else:
                                payload_data = {"raw": str(msg.payload)}
                        except Exception:
                            payload_data = {
                                "raw": (
                                    msg.payload.decode(errors="ignore")
                                    if isinstance(msg.payload, (bytes, bytearray))
                                    else str(msg.payload)
                                )
                            }
                        # Normalize topic to a string for browser clients
                        topic_obj = getattr(msg, "topic", None)
                        if isinstance(topic_obj, (bytes, bytearray)):
                            topic_str = topic_obj.decode("utf-8", "ignore")
                        elif isinstance(topic_obj, str):
                            topic_str = topic_obj
                        else:
                            topic_str = getattr(topic_obj, "value", str(topic_obj))
                        # Keep a copy of memory/results for REST consumers
                        if topic_str == config.memory_results_topic:
                            try:
                                # payload has shape { query, results: [{document, score}], k }
                                globals()["_last_memory_results"] = payload_data
                            except Exception:
                                pass
                        # Log health messages for debugging
                        if topic_str.startswith("system/health/"):
                            logger.info(f"Health message: {topic_str} -> {payload_data}")
                        logger.debug(f"Forwarding {topic_str}")
                        await manager.broadcast({"topic": topic_str, "payload": payload_data})
        except Exception as e:
            logger.error(f"MQTT bridge error: {e}")
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
