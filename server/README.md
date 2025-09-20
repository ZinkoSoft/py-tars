# Jetson STT Server (WebSocket)

This folder contains a WebSocket-based STT service designed to run on an NVIDIA Jetson (e.g., Orin Nano). It accepts streamed audio frames over WebSocket and returns partial and final transcriptions using Faster-Whisper.

## Why WebSocket?

- Keeps the Orange Pi 5 Max light: it streams VAD-gated audio and receives transcripts.
- Lets a GPU host (Jetson) handle Whisper decoding for lower latency and higher accuracy models.
- Loose coupling: the same client can point to localhost or an external Jetson just by changing an env var.

## Architecture

```
Client (Opi5)  → WS (PCM frames) →  Jetson STT Server (GPU Whisper)
                                 ←  partial/final JSON
```

Service: `stt-ws` (FastAPI + websockets + Faster-Whisper)

## Protocol

- Connect to: `ws://<jetson>:9000/stt`
- First message must be JSON `init`:

```json
{
  "type": "init",
  "session_id": "optional-id",
  "sample_rate": 16000,
  "lang": "en",
  "enable_partials": true
}
```

- Then send audio frames as WS binary messages containing raw PCM S16LE mono audio (20–40 ms per frame recommended).
- To end a segment, send JSON `{ "type": "end" }`. The server will respond with a final result.

Server → Client messages (JSON text):
- Partial: `{ "type": "partial", "text": "...", "confidence": 0.0, "t_ms": 0 }`
- Final:   `{ "type": "final",   "text": "...", "confidence": 0.0, "t_ms": 0 }`
- Health:  `{ "type": "health",  "ok": true }`

Notes:
- Confidence is an estimate; Faster-Whisper doesn’t emit calibrated confidences. Treat as heuristic.
- Timestamps are approximate based on buffer length.

## Run on Jetson

1. Ensure NVIDIA Container Runtime is installed and enabled for Docker.
2. Adjust `.env` and `docker-compose.yml` as needed.
3. Build and run:

```bash
docker compose -f server/docker-compose.yml --env-file server/.env up --build
```

Expose port 9000 to your LAN or reverse proxy as you prefer.

## Environment

- `WHISPER_MODEL` (default: `small`)
- `DEVICE` (default: `cuda`, fallback to `cpu`)
- `COMPUTE_TYPE` (default: `float16` if cuda else `int8`)
- `PARTIAL_INTERVAL_MS` (default: `300`)

Models directory can be cached inside container; for production, mount an NVMe-backed models volume and point Faster-Whisper cache there.

## Client integration

On the Orange Pi 5 Max client, set:
- `STT_BACKEND=ws`
- `WS_URL=ws://<jetson-ip>:9000/stt`

Then stream VAD-gated PCM frames to the WS and republish partials/finals to MQTT. (A `ws_transcriber.py` client can be added to `apps/stt-worker`.)

## Split into micro-services (optional)

This MVP runs everything in one container. You can split into:
- `stt-gateway`: WebSocket ingress + queue
- `stt-worker`: Whisper GPU worker(s)
- `redis`/`nats`: queue/bus between gateway and workers

Start simple, split when needed.
