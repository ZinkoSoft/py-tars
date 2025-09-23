# LLM Integration Plan

Goal: Add a flexible LLM capability that can be switched between:
- Local device (Raspberry Pi / Orange Pi)
- OpenAI API endpoint
- Server-hosted LLM (self-hosted or LAN server)
- Additional cloud providers: Google Gemini, xAI Grok, Alibaba Qwen (DashScope or OpenAI-compatible proxies)

The solution should use a common interface, be configurable via environment variables, integrate with existing MQTT topics (router + memory), and be resource-aware on constrained devices.

## 1) Architecture Overview

- New microservice: `llm-worker`
  - Connects to MQTT broker (same as other services)
  - Subscribes to conversation prompts (e.g., `llm/request`)
  - Performs retrieval-augmented generation (RAG) by querying `memory-worker` when enabled
  - Calls a provider backend to generate a response
  - Publishes responses to `llm/response` and TTS (`tts/say`) topics
  - Publishes health on `system/health/llm` (retained)

- Provider backends (pluggable):
  - `local`: on-device runtime (Pi/Orange Pi) via `llama.cpp` or `ollama` HTTP API or `llama-cpp-python`
  - `openai`: OpenAI-compatible API (OpenAI, Azure OpenAI, OpenRouter, xAI Grok, or other OpenAI-compatible endpoints)
  - `server`: Remote LAN/server-hosted LLM (Ollama/OpenRouter/vLLM/text-generation-inference), accessed over HTTP or gRPC
  - `gemini`: Google Generative AI (Gemini) via official REST/SDK
  - `dashscope`: Alibaba DashScope for Qwen models

- Configuration (env):
  - `LLM_PROVIDER` = local | openai | server | gemini | dashscope
  - `LLM_MODEL` = model id/name (provider-specific)
  - `LLM_MAX_TOKENS`, `LLM_TEMPERATURE`, `LLM_TOP_P`, `LLM_TOP_K`
  - `LLM_SERVER_URL` (for server provider), `OPENAI_API_KEY`, `OPENAI_BASE_URL` (optional)
  - `GEMINI_API_KEY`, `GEMINI_BASE_URL` (optional)
  - `DASHSCOPE_API_KEY`, `DASHSCOPE_BASE_URL` (optional)
  - `LLM_CTX_WINDOW`, `LLM_DEVICE` (cpu, gpu) when applicable
  - RAG toggles: `RAG_ENABLED`, `RAG_TOP_K`, `RAG_PROMPT_TEMPLATE`
  - Topics: `TOPIC_LLM_REQUEST`, `TOPIC_LLM_RESPONSE`

- Message contract:
  - Request payload (JSON): `{ "id": "<uuid>", "text": "...", "history": [...], "use_rag": true/false, "rag_k": 5, "system": "...", "params": { overrides... } }`
  - Response payload: `{ "id": "<uuid>", "reply": "...", "tokens": { "input": n, "output": m }, "latency_ms": t, "usage": {...}, "provider": "...", "model": "..." }`

## 2) Provider Abstraction

- Define a Python interface `LLMProvider`:
  - `generate(prompt: str, **kwargs) -> LLMResult`
  - Optional streaming: `stream(prompt: str, **kwargs) -> Iterable[LLMChunk]`
- Implementations:
  - `LocalProvider`: uses `llama-cpp-python` or `ollama` HTTP depending on env
    - For Pi/Orange Pi: recommend `ollama` on LAN server or small quantized model via llama.cpp; consider 4-bit quant (q4_0/q4_K_M)
  - `OpenAIProvider`: uses `openai` (with configurable `base_url`) for both OpenAI and Azure OpenAI/openai-compatible
  - `ServerProvider`: generic HTTP client to `LLM_SERVER_URL` supporting:
    - Ollama `/api/generate` or `/api/chat`
    - OpenRouter-compatible endpoints
    - vLLM or TGI APIs
  - `GeminiProvider`: Google Generative AI (Gemini) REST/SDK
    - Env: `GEMINI_API_KEY`, optional `GEMINI_BASE_URL`
    - Models: `gemini-1.5-pro`, `gemini-1.5-flash`, etc.
  - `DashScopeProvider`: Alibaba DashScope (Qwen family)
    - Env: `DASHSCOPE_API_KEY`, optional `DASHSCOPE_BASE_URL`
    - Models: `qwen2.5-*`, `qwen2-*` (instruct/chat)

- Minimal, provider-agnostic parameters: `model`, `max_tokens`, `temperature`, `top_p`, `top_k`, `stop`
  - Mapping notes:
    - Gemini: `max_output_tokens`, `temperature`, `topP`, `topK`
    - DashScope/Qwen: `max_tokens`, `temperature`, `top_p`, `top_k` (names vary slightly by endpoint)

## 3) RAG Integration

- When `use_rag` is true (or `RAG_ENABLED=1`):
  - Publish `memory/query` with `{ "text": prompt, "top_k": RAG_TOP_K }`
  - Wait for `memory/results` (correlate with ephemeral request id if needed, or rely on last-N cache)
  - Compose a prompt context section:
    - `RAG_PROMPT_TEMPLATE`, e.g.:
      """
      You are TARS. Use the following context to answer the user.
      Context:
      {context}

      User: {user}
      Assistant:
      """
  - Insert top-k docs summaries/snippets into `{context}`
  - Fall back gracefully if memory is unavailable or returns empty

## 4) MQTT Topics and Flow

- Topics:
  - `llm/request` (subscribe): incoming prompts
  - `llm/response` (publish): generated responses
  - `system/health/llm` (publish retained): service ready/error state
  - Uses existing `memory/query` and `memory/results` for RAG

- Flow:
  1. llm-worker receives `llm/request`
  2. Optional RAG: query memory and format augmented prompt
  3. Call selected provider to generate
  4. Publish `llm/response` with the answer
  5. Optionally forward to `tts/say` with `{"text": reply}` when desired

## 5) Local Provider Options

- Options ranked for Pi/Orange Pi:
  - Easiest: `ollama` on another LAN machine; llm-worker calls it via HTTP
  - On-device (heavier): `llama-cpp-python` with a small quantized model (Phi-2, TinyLlama, Qwen1.5-0.5B/1.8B) if memory allows
  - Jetson/ARM with GPU: consider `llama-cpp` with `metal`/`cuda` builds or `vLLM` on server

- Model handling:
  - For `ollama`, set `LLM_SERVER_URL=http://<host>:11434` and `LLM_MODEL` to an ollama model (e.g., `llama3:instruct` or `tinyllama:latest`)
  - For `llama-cpp-python`, mount models under `/models` and reference with `LLM_MODEL=/models/<gguf>`

## 6) OpenAI Provider

- Env:
  - `OPENAI_API_KEY`, optional `OPENAI_BASE_URL` for compatibility proxies
  - `LLM_MODEL` e.g. `gpt-4o-mini`, `gpt-4o`, `gpt-3.5-turbo`
- Features:
  - Streaming tokens support
  - Rate limiting/backoff
  - Optional tool/function call scaffolding later

## 7) Server Provider

- Env:
  - `LLM_SERVER_URL` pointing to an HTTP API
  - `LLM_MODEL` name
- Supported backends (shims):
  - Ollama `/api/generate` or `/api/chat`
  - OpenRouter-compatible (OpenAI schema with different base)
  - vLLM `/generate` or OpenAI-compatible
  - TGI `/generate` style

### 7.1) Gemini Provider (Google)

- Env:
  - `GEMINI_API_KEY` (required)
  - `GEMINI_BASE_URL` (optional, default Google endpoints)
  - `LLM_MODEL` e.g. `gemini-1.5-pro`, `gemini-1.5-flash`
- Features:
  - Text generation; multimodal later
  - Streaming via SDK/event stream → map to `llm/stream`
  - System instruction supported (map `system` accordingly)
- Parameters:
  - `max_tokens` → `max_output_tokens`; supports `temperature`, `topP`, `topK`

### 7.2) Grok Provider (xAI)

- Use as OpenAI-compatible:
  - `LLM_PROVIDER=openai`
  - `OPENAI_BASE_URL=https://api.x.ai/v1`
  - `OPENAI_API_KEY=<xai_key>`
  - Model names as per xAI docs
- Streaming: SSE delta mapping identical to OpenAI

### 7.3) Qwen Provider (Alibaba)

- Options:
  - `LLM_PROVIDER=dashscope` with `DASHSCOPE_API_KEY`
  - Or `LLM_PROVIDER=openai` with `OPENAI_BASE_URL` to a compatible proxy (e.g., OpenRouter)
  - Or `LLM_PROVIDER=server` to hit Ollama hosting Qwen
- Streaming supported; map streamed fragments to `llm/stream`

## 8) Config and Deployment

- New service `apps/llm-worker` with:
  - `requirements.txt` (aiohttp/httpx, pydantic, asyncio-mqtt, orjson, backoff)
  - `Dockerfile` similar to others
  - `config.py` (env parsing)
  - `providers/` folder: `base.py`, `local.py`, `openai.py`, `server.py`
  - `service.py` to wire MQTT and RAG

Provider-specific optional deps (add when implementing):
- Gemini: `google-generativeai`
- DashScope: `dashscope` (or use plain HTTP via `httpx`)

- Compose:
  - Add `llm` service with network_mode: host, env_file: .env, depends_on mqtt
  - Volumes for local models if using llama-cpp

## 9) Minimal Message Contract & Types

- Request:
  - `id: str (uuid)`
  - `text: str`
  - `history: list[turns]` (optional)
  - `use_rag: bool` (optional)
  - `rag_k: int` (optional)
  - `system: str` (optional)
  - `params: dict` (optional overrides per-request)

- Response:
  - `id: str`
  - `reply: str`
  - `error: str | None`
  - `provider: str`
  - `model: str`
  - `tokens: { input: int, output: int }` (when available)
  - `latency_ms: int`

## 10) Error Handling & Observability

- Timeouts and retries for provider calls
- Backoff for transient network errors
- Health topic updates on fatal errors
- Basic metrics: count, latency histograms (log-based for now)
- Optional tracing later

## 11) Roadmap & Milestones

- M1: Scaffold llm-worker with provider interface and OpenAI provider
  - Implement MQTT plumbing, non-streaming generation
  - Basic RAG query to memory-worker
  - Smoke test with OpenAI cheap model (gpt-4o-mini)

- M2: Add Server provider (Ollama) and test with LAN Ollama
  - HTTP client with JSON schema mapping
  - Prompt template support

- M2.5: Add Gemini provider
  - REST/SDK client, params/role mapping, streaming
  - Backoff/quota handling

- M3: Add Local provider (llama-cpp-python)
  - GGUF model mounting & configuration
  - Optional streaming

- M3.5: Add Qwen via DashScope provider
  - REST client, parameter mapping, streaming
  - Alternative path via OpenAI-compatible proxy (OpenRouter)

- M4: Streaming responses end-to-end
  - Token/segment stream via MQTT (e.g., `llm/stream`) and UI/TTS consumption

- M5: Tool use hooks
  - Structured tool call contract in request/response
  - Router orchestration updates

- M6: Server WebSocket gateway (`server/llm-ws`)
  - WebSocket API for chat with streaming (`chat.delta`), auth, and provider selection
  - Bridges to same provider adapters (OpenAI/Ollama/Local) and optional RAG via memory-worker

## 12) Security & Limits

- Don’t log secrets (API keys)
- Enforce max prompt/response sizes
- Guardrails for unsafe content (basic filtering initially)

## 13) Testing Strategy

- Unit tests for provider adapters (mock HTTP)
- Integration tests using a local stub server for OpenAI-compatible endpoints
- MQTT smoke tests: publish `llm/request`, assert `llm/response` within timeout

## 14) Deliverables (initial PR)

- `apps/llm-worker/` skeleton with OpenAI provider
- Compose service entry
- `.env.example` with provider envs
- Minimal README with topic contract and usage
- Basic smoke test script under `ops/`

## 15) Streaming Responses and TTS Chunking

Goal: stream LLM output in near real-time so the TTS worker can speak in chunks, reducing perceived latency.

Design principles:
- Provider-agnostic streaming interface with graceful fallback to non-streaming.
- Keep message payloads small and frequent; include ordering (`seq`) and `id` for correlation.
- Provide end-of-stream markers and error semantics.
- Allow cancellation (user interrupt or new prompt).

Topics:
- `llm/request`: accepts `{ "id", "text", ..., "stream": true }` to request streaming.
- `llm/stream`: emits streaming chunks.
- `llm/response`: emits the final full reply and usage once done (optional when streaming).
- `llm/cancel`: `{ "id": "..." }` to stop an in-flight generation.
- `tts/stream` (optional, recommended): LLM worker forwards sentence-level chunks for speech.

Message contracts:
- Request (streaming enabled):
  ```json
  { "id": "<uuid>", "text": "...", "stream": true, "use_rag": true, "rag_k": 5, "system": "...", "params": { "max_tokens": 256, "temperature": 0.7 } }
  ```

- Stream chunk on `llm/stream`:
  ```json
  { "id": "<uuid>", "seq": 12, "delta": "text fragment", "done": false, "provider": "openai", "model": "gpt-4o-mini" }
  ```

- Stream end:
  ```json
  { "id": "<uuid>", "seq": 999999, "done": true, "usage": { "input": 123, "output": 456 }, "latency_ms": 1875 }
  ```

- Error (sent as a chunk and followed by `done`):
  ```json
  { "id": "<uuid>", "seq": 42, "error": "provider timeout", "done": false }
  ```

- Cancellation:
  - Publish to `llm/cancel`: `{ "id": "<uuid>" }`
  - Worker stops streaming, emits a final `done` chunk with `reason: "cancelled"`.

TTS integration strategies:
- Simple: Buffer tokens into sentence-like segments and publish to `tts/say` as soon as a sentence completes.
- Recommended: Use `tts/stream` with a sentence-aware contract:
  ```json
  { "id": "<uuid>", "seq": 7, "text": "Complete sentence or phrase.", "is_boundary": true, "end": false }
  ```

Chunking heuristics (configurable):
- Flush when encountering boundary punctuation [., !, ?, ;, :], or when min/max character thresholds are met.
- Time-based flush: if no new tokens after `STREAM_FLUSH_TIMEOUT_MS` (e.g., 250–400ms), push current buffer.
- Config keys: `STREAM_MIN_CHARS` (e.g., 60), `STREAM_MAX_CHARS` (e.g., 240), `STREAM_BOUNDARY_CHARS` (punctuation set), `STREAM_FLUSH_TIMEOUT_MS`.

Provider support mapping:
- OpenAI: use `stream=true` and handle SSE deltas (`choices[].delta.content`). Emit chunks as `delta` arrives; send `done` on `[DONE]`.
- Ollama: set `stream=true` and read line-delimited JSON with `done` flag; map `response` field to `delta`.
- llama-cpp-python: use the token callback/iterator API; aggregate tokens into `delta` chunks.
 - Gemini: use SDK/event stream or streaming REST; map streamed content parts to `delta`.
 - DashScope (Qwen): use streaming REST; map streamed fragments to `delta`.

Backpressure and QoS:
- Keep chunk size small; ensure chunk rate does not exceed TTS playback capacity.
- Optionally implement a simple in-memory per-id queue with max depth; drop or coalesce if overflow.
- MQTT QoS 0 or 1 is sufficient; include `seq` for re-order protection on consumer side.

RAG with streaming:
- Perform memory retrieval before starting the provider stream.
- Prepend context to the prompt and then stream the assistant response only.

MVP acceptance (M4):
- End-to-end: `llm/request` with `stream=true` produces `llm/stream` chunks and at least sentence-level `tts/stream` messages.
- Cancellation via `llm/cancel` stops ongoing generation within ~250ms and emits `done`.

Operational notes:
- Health topic includes last-stream status and last error.
- Log chunk counts, average chunk size, first-byte latency, and total latency.

## 16) Server WebSocket Gateway: `server/llm-ws`

Purpose: Expose a lightweight WebSocket API for chat completion with token streaming to serve web clients or external apps. Keeps the same provider choices (OpenAI/server/local) behind a single WS interface.

Tech stack:
- Python FastAPI or Starlette with WebSocket support (uvicorn)
- httpx/aiohttp for HTTP provider calls
- orjson for serialization; backoff for retries
- Optional MQTT client if doing RAG via memory-worker

Endpoints:
- WS: `ws://<host>:<port>/ws` (default port 9001)
- Optional HTTP health: `GET /healthz` returns `{ ok: true }`

WS protocol (JSON frames):
- auth (optional if deployed on trusted LAN):
  ```json
  { "type": "auth", "token": "<bearer>" }
  ```
- start chat:
  ```json
  {
    "type": "chat.start",
    "id": "<uuid>",
    "model": "<name>",
    "provider": "openai|server|local",
    "text": "<user prompt>",
    "history": [],
    "stream": true,
    "use_rag": true,
    "rag_k": 5,
    "system": "You are TARS.",
    "params": { "max_tokens": 256, "temperature": 0.7 }
  }
  ```
- stream delta:
  ```json
  { "type": "chat.delta", "id": "<uuid>", "seq": 3, "delta": "text fragment" }
  ```
- done:
  ```json
  { "type": "chat.done", "id": "<uuid>", "usage": { "input": 123, "output": 456 }, "latency_ms": 1875 }
  ```
- error:
  ```json
  { "type": "error", "id": "<uuid>", "message": "provider timeout" }
  ```
- cancel:
  ```json
  { "type": "chat.cancel", "id": "<uuid>" }
  ```

Auth:
- Support `Authorization: Bearer <token>` header on initial HTTP upgrade, and/or an `auth` frame.
- Env: `LLM_WS_TOKEN` or `LLM_WS_TOKENS` (comma-separated) for shared-secret access.
- CORS: allow configured origins via `ALLOWED_ORIGINS`.

Providers:
- Reuse the same provider abstraction as `llm-worker` (shared module or duplicated minimal shim initially).
- `provider=openai`: forward to OpenAI-compatible API with stream SSE → emit `chat.delta` frames.
- `provider=server`: call Ollama/vLLM/TGI endpoints with streaming; map to frames.
- `provider=local`: optional llama-cpp binding if running on the same host.

RAG options:
- Option A (preferred): WS server publishes `memory/query` via MQTT, waits for `memory/results`, then prepends context to prompt before starting the provider stream.
- Option B: clients provide context; WS simply streams the model’s answer.

Config/env:
- `LLM_PROVIDER`, `LLM_MODEL`, `LLM_SERVER_URL`, `OPENAI_API_KEY`, `OPENAI_BASE_URL`
- `LLM_WS_PORT=9001`, `LLM_WS_TOKEN`, `ALLOWED_ORIGINS` (CSV)
- RAG: `RAG_ENABLED`, `RAG_TOP_K`, broker URL vars for memory integration

Deployment:
- Path: `server/llm-ws/`
  - `Dockerfile`, `requirements.txt`, `main.py` (FastAPI app), `providers/`
- Compose:
  - Add a service `llm-ws` in `server/docker-compose.yml` (similar to `stt-ws`), map `${LLM_WS_PORT}:9001`, env_file `.env`
  - Depends on network reachability to MQTT (for RAG)

MVP acceptance:
- A simple web client can connect, send `chat.start` with `stream=true`, receive `chat.delta` frames and a `chat.done` frame.
- If `use_rag=true`, top-k memory snippets are fetched and included.

## 17) SSE vs WebSockets

Question: Should we use Server-Sent Events (SSE) instead of WebSockets for streaming tokens?

Recommendation: Support both; default to WebSockets, offer SSE as a simpler alternative for one-way streaming from server to client.

Pros SSE:
- Simpler to implement and consume (EventSource in browsers), one-way stream matches token emission.
- Works well with proxies/CDNs; plain HTTP semantics.
- Easy retry/reconnect semantics.

Pros WebSockets:
- Full duplex: supports chat.cancel, dynamic parameter changes, client pings.
- Lower overhead for high-frequency small messages.
- Easier multiplexing of control and data frames.

When to choose SSE:
- Simple web clients that just need a stream of tokens for a single request.
- Environments where WS upgrade is problematic due to proxies or restrictive networks.

Design for SSE endpoint (alongside WS):
- HTTP GET `/sse/chat` with query/body params:
  - Query: `id`, `model`, `provider`, `use_rag`, `rag_k`, optional `system` and generation params.
  - Body: JSON `{ text: "...", history: [...] }` (or allow POST `/sse/chat` that responds with event-stream)
- Response headers: `Content-Type: text/event-stream`, `Cache-Control: no-cache`
- Events:
  - `event: delta\n data: {"id":"...","seq":n,"delta":"..."}\n\n`
  - Final: `event: done\n data: {"id":"...","usage":{...}}\n\n`
  - Error: `event: error\n data: {"id":"...","message":"..."}\n\n`
- Cancellation with SSE:
  - Use a companion HTTP endpoint `POST /chat/cancel` with `{ id }`, or accept a `Last-Event-ID` reconnection strategy.
  - If duplex cancel is required, prefer WS.

Implementation note:
- In `server/llm-ws`, add an SSE router (FastAPI `EventSourceResponse` or Starlette StreamingResponse) that shares provider code with WS.
- Keep output format aligned with WS deltas to reduce codepaths.
