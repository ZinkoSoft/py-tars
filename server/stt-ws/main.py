import asyncio
import logging
import os
import time
from typing import Optional

import numpy as np
import orjson
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.responses import JSONResponse
from fastapi.websockets import WebSocketState
from faster_whisper import WhisperModel

app = FastAPI(title="Jetson STT WS")
logger = logging.getLogger("stt-ws")
logging.basicConfig(level=os.getenv("LOG_LEVEL", "INFO"))

WHISPER_MODEL = os.getenv("WHISPER_MODEL", "small")
DEVICE = os.getenv("DEVICE", "auto")  # let faster-whisper/ctranslate2 decide (cuda if available)
COMPUTE_TYPE = os.getenv("COMPUTE_TYPE", "auto")  # let library pick best (fp16 on GPU, int8 on CPU)
PARTIAL_INTERVAL_MS = int(os.getenv("PARTIAL_INTERVAL_MS", "300"))

model: Optional[WhisperModel] = None


def load_model():
    global model
    if model is None:
        try:
            model = WhisperModel(WHISPER_MODEL, device=DEVICE, compute_type=COMPUTE_TYPE)
        except Exception:
            # Graceful fallback in case auto detection fails in container runtime
            model = WhisperModel(WHISPER_MODEL, device="cpu", compute_type="int8")


@app.get("/health")
async def health():
    try:
        load_model()
        return {"ok": True, "model": WHISPER_MODEL, "device": DEVICE, "compute_type": COMPUTE_TYPE}
    except Exception as e:
        return JSONResponse(status_code=500, content={"ok": False, "err": str(e)})


@app.get("/")
async def root():
    return {"service": "stt-ws", "ok": True, "endpoints": ["/health", "/stt (websocket)"]}


@app.get("/live")
async def live():
    # Liveness probe that doesn't load model
    return {"ok": True}


@app.get("/ready")
async def ready():
    # Readiness probe that ensures model can be loaded
    return await health()


class Session:
    def __init__(self, sample_rate: int, lang: str | None, enable_partials: bool):
        self.sample_rate = sample_rate
        self.lang = lang
        self.enable_partials = enable_partials
        self.buf = bytearray()
        self.last_partial_ts = 0.0

    def append(self, pcm: bytes):
        self.buf.extend(pcm)

    def clear(self):
        self.buf.clear()

    def duration_ms(self) -> float:
        return (len(self.buf) / 2) / max(1, self.sample_rate) * 1000.0


async def transcribe_bytes(pcm: bytes, sample_rate: int, language: Optional[str]):
    load_model()
    # Convert PCM16LE bytes to float32 numpy array scaled to -1..1
    audio = np.frombuffer(pcm, dtype=np.int16).astype(np.float32) / 32768.0
    segments, info = model.transcribe(
        audio,
        language=language,
        vad_filter=True,
        vad_parameters=dict(min_silence_duration_ms=250),
        no_speech_threshold=0.45,
        beam_size=5,
        best_of=5,
        condition_on_previous_text=True,
        temperature=0.0,
        word_timestamps=False,
    )
    text = "".join(s.text for s in segments).strip()
    # Faster-Whisper doesn't expose calibrated confidence; use avg_logprob heuristics if needed
    conf = getattr(info, "language_probability", None)
    return text, conf


@app.websocket("/stt")
async def stt_ws(ws: WebSocket):
    await ws.accept()
    session: Optional[Session] = None
    try:
        while True:
            msg = await ws.receive()
            mtype = msg.get("type")
            if mtype == "websocket.disconnect":
                break

            text_frame = msg.get("text")
            bytes_frame = msg.get("bytes")

            if text_frame is not None:
                # Control messages come as text JSON
                try:
                    data = orjson.loads(text_frame) if isinstance(text_frame, str) else text_frame
                except Exception:
                    await ws.send_text(orjson.dumps({"type": "error", "err": "invalid json"}).decode())
                    continue
                mt = data.get("type")
                if mt == "init":
                    sr = int(data.get("sample_rate", 16000))
                    lang = data.get("lang")
                    enable_partials = bool(data.get("enable_partials", True))
                    session = Session(sr, lang, enable_partials)
                    logger.info(f"session init: sr={sr} lang={lang} partials={enable_partials}")
                    await ws.send_text(orjson.dumps({"type": "health", "ok": True}).decode())
                elif mt == "end":
                    if session and session.buf:
                        buf_len = len(session.buf)
                        logger.info(f"end received: transcribing {buf_len} bytes")
                        text, conf = await transcribe_bytes(bytes(session.buf), session.sample_rate, session.lang)
                        await ws.send_text(orjson.dumps({
                            "type": "final",
                            "text": text,
                            "confidence": conf,
                            "t_ms": int(session.duration_ms()),
                            "bytes": buf_len
                        }).decode())
                        logger.info(f"final sent: text_len={len(text)}")
                        session.clear()
                    else:
                        logger.info("end received: empty buffer")
                        await ws.send_text(orjson.dumps({"type": "final", "text": "", "confidence": None, "t_ms": 0, "bytes": 0}).decode())
                else:
                    await ws.send_text(orjson.dumps({"type": "error", "err": "unknown message type"}).decode())

            elif bytes_frame is not None:
                # Audio frames come as binary
                if ws.client_state != WebSocketState.CONNECTED:
                    break
                if not session:
                    await ws.send_text(orjson.dumps({"type": "error", "err": "send init first"}).decode())
                    continue
                if not bytes_frame:
                    continue
                session.append(bytes_frame)
                logger.debug(f"audio bytes appended: +{len(bytes_frame)} total={len(session.buf)}")
                now = time.time()
                if session.enable_partials and ((now - session.last_partial_ts) * 1000.0) >= PARTIAL_INTERVAL_MS:
                    # Transcribe current buffer for a partial
                    text, conf = await transcribe_bytes(bytes(session.buf), session.sample_rate, session.lang)
                    if text:
                        await ws.send_text(orjson.dumps({
                            "type": "partial",
                            "text": text,
                            "confidence": conf,
                            "t_ms": int(session.duration_ms())
                        }).decode())
                        logger.debug(f"partial sent: len={len(text)} t_ms={int(session.duration_ms())}")
                    session.last_partial_ts = now

    except WebSocketDisconnect:
        pass
    except Exception as e:
        try:
            await ws.send_text(orjson.dumps({"type": "error", "err": str(e)}).decode())
        except Exception:
            pass


if __name__ == "__main__":
    import uvicorn
    # Lazily load on first request to speed container boot; uvicorn will call app instance
    uvicorn.run("main:app", host="0.0.0.0", port=9000, reload=False)
