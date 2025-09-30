# Camera Vision Expansion Plan

Goal: Deliver live video, still photo capture, and vision-assisted responses for TARS using the Orange Pi camera, while offloading heavy inference to the Jetson vision stack or another LAN-accessible LLM service.

## 1) Architecture Overview

- **Camera capture (Orange Pi)**: Python `camera-service` owns Picamera2 capture, provides WebRTC signaling, exposes REST/WebSocket control endpoints, and publishes MQTT health/status.
- **Transport**: WebRTC with H.264 (hardware-accelerated) for video and Opus/PCM for audio; TURN optional for WAN access; DataChannel for low-latency controls.
- **UI consumption**: `apps/ui-web` negotiates WebRTC sessions, renders live feed, and issues capture/describe commands; MQTT/WebSocket updates keep UI reactive.
- **Vision inference**: Jetson-hosted HTTP service (or other web LLM) handles captions/QA; camera-service/router forward signed image URLs and prompts.
- **Integration glue**: Router coordinates voice/LLM prompts with camera events; memory worker can store vision-derived metadata if needed.

## 2) Service Responsibilities

| Service | Responsibilities |
| --- | --- |
| `apps/camera-service` | Capture/encode video, manage WebRTC peers, capture stills, persist images, publish MQTT events, forward requests to vision service |
| `apps/ui-web` | User-facing viewer, command UI, WebRTC signaling client, display of captured photos and captions |
| Router | Interpret user intents ("what do you see?"), orchestrate capture + vision calls, merge responses into conversation |
| Jetson vision API | REST endpoints for captioning/QA, model selection, authentication, response formatting |
| MQTT broker | Control plane events (`camera/command`, `camera/event`, `camera/health`) |

## 3) WebRTC Streaming Design

- **Signaling flow**: UI POSTs SDP offer to `/webrtc/offer`; camera-service answers with SDP; ICE candidates exchanged over same REST/WebSocket channel.
- **Media pipeline**: Picamera2 → GStreamer/aiortc → WebRTC; use hardware H.264 encoder when available, fallback to MJPEG at reduced resolution.
- **Session control**: DataChannel handles pause/resume, resolution changes, capture triggers; idle timeout tears down unused sessions.
- **Configuration knobs**: `CAMERA_RES_X/Y`, `CAMERA_FPS`, `CAMERA_BITRATE`, `CAMERA_HW_ENCODER`, `TURN_URL`, `TURN_CREDENTIALS`.
- **Health & metrics**: Publish `system/health/camera`, log first-frame latency, track peer count, emit warnings on encoder fallback.

## 4) Still Capture & Vision Pipeline

1. UI button or LLM intent publishes `camera/command` (`{"command":"capture","id":...}`) or hits REST endpoint.
2. camera-service grabs frame, saves to `/data/camera/<timestamp>.jpg`, generates signed URL, publishes `camera/event` with metadata.
3. Router (for voice/chat commands) calls Jetson `POST /vision/caption` (or `/vision/qa`) with image URL + user prompt, awaits structured response `{ caption, confidence, details }`.
4. Router merges vision response into conversation, publishes `llm/response` and optionally `tts/say`.
5. UI subscribes to MQTT/WebSocket updates to display photo thumbnail and caption; allow download/view in gallery.

## 5) API & Contract Notes

- **MQTT topics**
  - `camera/health` (retained): `{ "ok": bool, "event": str, "ts": float }`
  - `camera/command`: `{ "id": uuid, "command": "start|stop|capture|describe", "params": {...} }`
  - `camera/event`: `{ "id": uuid, "type": "capture|stream_status", "image_url": str?, "status": str, "ts": float }`
- **REST/WebSocket**
  - `POST /webrtc/offer`, optional `WS /ws/signaling` for full-duplex signaling
  - `POST /capture` → returns `{ "image_url": str, "id": uuid }`
  - `POST /vision/describe` (proxy to Jetson) → returns Jetson response, handles retries/timeouts
- **Vision service contract** (Jetson)
  - Request: `{ "image_url": str, "prompt": str, "mode": "caption|qa" }`
  - Response: `{ "caption": str, "qa": str?, "confidence": float?, "raw": {...} }`
  - Auth via bearer token or mTLS; configurable base URL

## 6) Configuration & Deployment

- `.env` additions: `CAMERA_SIGNALLING_PORT`, `CAMERA_DATA_DIR`, `CAMERA_JETSON_URL`, `CAMERA_JETSON_TOKEN`, `TURN_URL`, `TURN_USER`, `TURN_PASS`.
- Docker: new `docker/specialized/camera-service.Dockerfile`, host networking for low-latency camera access; mount `/dev/video*` or Picamera2 resources.
- Compose updates: add service, ensure dependencies on MQTT and optionally TURN; update `apps/ui-web` env to point to signaling endpoint.
- Permissions: configure `udev` rules for camera access; ensure data dir writable; handle SELinux/AppArmor if applicable.

## 7) Security, Observability, Reliability

- Enforce auth on signaling/capture endpoints (shared token or OAuth in LAN gateway).
- Sign image URLs with short-lived tokens; optionally require authenticated proxy to fetch.
- Never log raw image data; redact tokens.
- Structured logging (JSON) with `request_id`, `session_id`, `peer_id`.
- Metrics: stream uptime, capture success rate, Jetson latency, error counts.
- Graceful degradation: if Jetson unavailable, return fallback message and keep streaming; if hardware encode fails, automatically reduce resolution/FPS.

## 8) Implementation Phases

1. **M1 – Service scaffold & capture basics**
   - Initialize `camera-service` project, env config, health MQTT, simple JPEG capture API.
   - Manual testing with Picamera2 capture, verify image persistence.

2. **M2 – WebRTC streaming MVP**
   - Add WebRTC signaling endpoints, integrate aiortc/GStreamer pipeline.
   - Implement UI WebRTC client with live preview; basic start/stop controls.

3. **M3 – Command + event plumbing**
   - Wire MQTT command/event topics; UI buttons publish via router or direct MQTT.
   - DataChannel control path; still capture triggered during active stream.

4. **M4 – Vision inference integration**
   - Implement Jetson vision client with retries/backoff; expose `/vision/describe` proxy.
   - Update router workflows to service voice/chat prompts with captured images.
   - Display captions in UI; add gallery/history view.

5. **M5 – Hardening & remote access**
   - Add TURN support, auth, TLS termination, retention policy for stored images.
   - Expand tests (unit + integration), document operations, ensure Make targets.
   - Performance tuning (bitrate adapt, watchdogs, metrics dashboards).

## 9) Risks & Open Questions

- **Hardware acceleration availability**: confirm Orange Pi distro provides V4L2/VA-API for H.264; otherwise plan for MJPEG fallback.
- **Bandwidth constraints**: WAN streaming may require adaptive bitrate or on-demand snapshots instead of continuous video.
- **Vision model latency**: Jetson throughput must meet conversational expectations; consider batching or async responses.
- **Storage & privacy**: define retention/cleanup policy for captured images; confirm user consent requirements.
- **TURN/ICE complexity**: determine if remote access is in scope for Phase M5 or future iteration.
