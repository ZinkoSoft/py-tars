# MQTT Topic Registry

**Version**: 1.0  
**Last Updated**: 2024-10-16  
**Status**: Active

This document serves as the authoritative registry of all MQTT topics used in the py-tars system.

---

## Topic Naming Convention

All topics follow the pattern: `<domain>/<action>`

- **domain**: The service or functional area (stt, tts, llm, memory, wake, camera, movement, system)
- **action**: The operation or event type (final, partial, say, status, request, response, event, etc.)

**Exception**: Tool-related topics use dots for sub-namespacing: `llm/tool.call.request`

---

## Speech-to-Text (STT) Domain

### `stt/final`
- **Publisher**: STT Worker
- **Subscribers**: Router, UI, UI-Web
- **QoS**: 1 (reliable delivery)
- **Retained**: No
- **Contract**: `FinalTranscript` from `tars.contracts.v1.stt`
- **Purpose**: Final transcription result after utterance completion
- **Fields**:
  - `message_id`: Unique identifier (auto-generated)
  - `text`: Transcribed text
  - `lang`: Language code (default: "en")
  - `confidence`: Recognition confidence (0.0-1.0)
  - `utt_id`: Utterance ID (optional, for correlation)
  - `ts`: Timestamp
  - `is_final`: Always true for this topic

### `stt/partial`
- **Publisher**: STT Worker
- **Subscribers**: Router, UI
- **QoS**: 0 (streaming, best effort)
- **Retained**: No
- **Contract**: `PartialTranscript` from `tars.contracts.v1.stt`
- **Purpose**: Streaming partial transcripts during active speech
- **Fields**: Same as `stt/final` but `is_final=false`
- **Note**: Disabled when using WebSocket backend

### `stt/audio_fft`
- **Publisher**: STT Worker
- **Subscribers**: UI (for visualization)
- **QoS**: 0 (streaming, best effort)
- **Retained**: No
- **Contract**: `AudioFFTData` from `tars.contracts.v1.stt`
- **Purpose**: Real-time audio FFT data for waveform visualization
- **Fields**:
  - `message_id`: Unique identifier
  - `fft_data`: FFT magnitude values (list of floats)
  - `sample_rate`: Audio sample rate in Hz
  - `ts`: Timestamp

---

## Text-to-Speech (TTS) Domain

### `tts/say`
- **Publisher**: Router, LLM Worker
- **Subscribers**: TTS Worker
- **QoS**: 1 (commands require reliable delivery)
- **Retained**: No
- **Contract**: `TtsSay` from `tars.contracts.v1.tts`
- **Purpose**: Command to synthesize and play speech
- **Fields**:
  - `message_id`: Unique identifier
  - `text`: Text to synthesize
  - `voice`: Voice model name (optional, uses configured default)
  - `lang`: Language code (optional)
  - `utt_id`: Utterance ID for response aggregation
  - `style`: Speaking style (optional)
  - `stt_ts`: Original STT timestamp (for latency tracking)

### `tts/status`
- **Publisher**: TTS Worker
- **Subscribers**: Router, STT Worker, UI
- **QoS**: 0 (status updates are streaming)
- **Retained**: No
- **Contract**: `TtsStatus` from `tars.contracts.v1.tts`
- **Purpose**: Real-time status updates during speech synthesis
- **Fields**:
  - `message_id`: Unique identifier
  - `event`: "speaking_start" | "speaking_end"
  - `text`: Text being spoken
  - `utt_id`: Utterance ID
  - `ts`: Timestamp

### `tts/control`
- **Publisher**: Router, Wake Activation
- **Subscribers**: TTS Worker
- **QoS**: 1 (control commands require reliable delivery)
- **Retained**: No
- **Contract**: `TtsControlCommand` from `tars.contracts.v1.tts`
- **Purpose**: Control commands for TTS (stop, cancel, etc.)
- **Fields**:
  - `message_id`: Unique identifier
  - `command`: "stop" | "pause" | "resume" | "cancel"
  - `utt_id`: Target utterance ID (optional, for selective control)

---

## Large Language Model (LLM) Domain

### `llm/request`
- **Publisher**: Router
- **Subscribers**: LLM Worker
- **QoS**: 1 (requests require reliable delivery)
- **Retained**: No
- **Contract**: `LLMRequest` from `tars.contracts.v1.llm`
- **Purpose**: Request LLM inference (streaming or non-streaming)
- **Fields**:
  - `id`: Request ID (used for correlation with responses)
  - `message_id`: Unique message identifier
  - `text`: Input prompt
  - `stream`: Enable streaming responses (default: false)
  - `use_rag`: Query memory/RAG (default: false)
  - `system`: System prompt override (optional)
  - `params`: Generation parameters (temperature, max_tokens, etc.)
  - `messages`: Conversation history (optional)

### `llm/response`
- **Publisher**: LLM Worker
- **Subscribers**: Router
- **QoS**: 1 (responses require reliable delivery)
- **Retained**: No
- **Contract**: `LLMResponse` from `tars.contracts.v1.llm`
- **Purpose**: Complete LLM response (non-streaming)
- **Fields**:
  - `id`: Request ID (correlates with request)
  - `message_id`: Unique message identifier
  - `reply`: Generated response text
  - `error`: Error message (if inference failed)
  - `provider`: LLM provider name
  - `model`: Model name
  - `tokens`: Token usage stats (optional)

### `llm/stream`
- **Publisher**: LLM Worker
- **Subscribers**: Router
- **QoS**: 0 (streaming deltas, best effort)
- **Retained**: No
- **Contract**: `LLMStreamDelta` from `tars.contracts.v1.llm`
- **Purpose**: Streaming response deltas
- **Fields**:
  - `id`: Request ID (correlates with request)
  - `message_id`: Unique message identifier
  - `seq`: Sequence number
  - `delta`: Text chunk
  - `done`: Final delta indicator

### `llm/cancel`
- **Publisher**: Router
- **Subscribers**: LLM Worker
- **QoS**: 1 (cancellation requires reliable delivery)
- **Retained**: No
- **Contract**: `LLMCancel` from `tars.contracts.v1.llm`
- **Purpose**: Cancel in-progress LLM request
- **Fields**:
  - `id`: Request ID to cancel
  - `message_id`: Unique message identifier

### `llm/tool.call.request`
- **Publisher**: LLM Worker
- **Subscribers**: Router, MCP Bridge
- **QoS**: 1 (tool calls require reliable delivery)
- **Retained**: No
- **Contract**: `ToolCallRequest` from `tars.contracts.v1.mcp`
- **Purpose**: Request tool/function execution
- **Fields**:
  - `call_id`: Unique call identifier
  - `name`: Tool name
  - `arguments`: Tool arguments (JSON object)

### `llm/tool.call.result`
- **Publisher**: MCP Bridge, Router
- **Subscribers**: LLM Worker
- **QoS**: 1 (tool results require reliable delivery)
- **Retained**: No
- **Contract**: `ToolCallResult` from `tars.contracts.v1.mcp`
- **Purpose**: Tool execution result
- **Fields**:
  - `call_id`: Correlates with request
  - `result`: Tool output (JSON)
  - `error`: Error message (if tool failed)

### `llm/tools/registry`
- **Publisher**: MCP Bridge
- **Subscribers**: LLM Worker
- **QoS**: 1 (retained)
- **Retained**: Yes
- **Contract**: `ToolsRegistry` from `tars.contracts.v1.mcp`
- **Purpose**: Available tools registry (updated dynamically)
- **Fields**:
  - `tools`: List of `ToolSpec` objects
  - Each ToolSpec: `name`, `description`, `parameters`

---

## Memory/RAG Domain

### `memory/query`
- **Publisher**: LLM Worker
- **Subscribers**: Memory Worker
- **QoS**: 1 (queries require reliable delivery)
- **Retained**: No
- **Contract**: `MemoryQuery` from `tars.contracts.v1.memory`
- **Purpose**: Query memory for relevant context
- **Fields**:
  - `message_id`: Unique identifier
  - `text`: Query text
  - `top_k`: Number of results (default: 5)
  - `threshold`: Similarity threshold (optional)

### `memory/results`
- **Publisher**: Memory Worker
- **Subscribers**: LLM Worker
- **QoS**: 1 (results require reliable delivery)
- **Retained**: No
- **Contract**: `MemoryResults` from `tars.contracts.v1.memory`
- **Purpose**: Memory query results
- **Fields**:
  - `message_id`: Unique identifier (correlates with query)
  - `query`: Original query text
  - `k`: Number of results returned
  - `results`: List of `MemoryResult` objects
  - Each result: `document` (text + metadata), `score` (similarity)

---

## Wake Word Domain

### `wake/event`
- **Publisher**: Wake Activation
- **Subscribers**: Router, STT Worker, UI
- **QoS**: 1 (wake events require reliable delivery)
- **Retained**: No
- **Contract**: `WakeEvent` from `tars.contracts.v1.wake`
- **Purpose**: Wake word detected
- **Fields**:
  - `message_id`: Unique identifier
  - `type`: Event type (always "wake.event")
  - `confidence`: Detection confidence
  - `ts`: Timestamp

### `wake/mic`
- **Publisher**: Wake Activation, Router
- **Subscribers**: STT Worker
- **QoS**: 1 (mic control requires reliable delivery)
- **Retained**: No
- **Contract**: `WakeMicCommand` from `tars.contracts.v1.wake`
- **Purpose**: Control microphone state (enable/disable listening)
- **Fields**:
  - `message_id`: Unique identifier
  - `command`: "enable" | "disable"

---

## Camera Domain

### `camera/frame`
- **Publisher**: Camera Service
- **Subscribers**: Vision processors, UI
- **QoS**: 0 (streaming frames, best effort)
- **Retained**: No
- **Contract**: `CameraFrame` from `tars.contracts.v1.camera`
- **Purpose**: Real-time camera frame data
- **Fields**:
  - `message_id`: Unique identifier
  - `frame_data`: Base64-encoded image
  - `format`: Image format ("jpeg", "png", etc.)
  - `width`: Frame width in pixels
  - `height`: Frame height in pixels
  - `ts`: Capture timestamp

### `camera/capture`
- **Publisher**: Controller/User
- **Subscribers**: Camera Service
- **QoS**: 1 (capture commands require reliable delivery)
- **Retained**: No
- **Contract**: `CameraCaptureRequest` from `tars.contracts.v1.camera`
- **Purpose**: Request camera capture
- **Fields**:
  - `message_id`: Unique identifier (used for response correlation)
  - `format`: Desired image format
  - `quality`: Quality setting (optional)

### `camera/image`
- **Publisher**: Camera Service
- **Subscribers**: Requestor
- **QoS**: 1 (captured images require reliable delivery)
- **Retained**: No
- **Contract**: `CameraImageResponse` from `tars.contracts.v1.camera`
- **Purpose**: Captured image result
- **Fields**:
  - `message_id`: Correlates with request
  - `image_data`: Base64-encoded image
  - `format`: Image format
  - `width`, `height`: Dimensions
  - `ts`: Capture timestamp

---

## Movement Domain

### `movement/command`
- **Publisher**: LLM Worker (via tools), Router
- **Subscribers**: Movement Service
- **QoS**: 1 (movement commands require reliable delivery)
- **Retained**: No
- **Contract**: `MovementCommand` from `tars.contracts.v1.movement`
- **Purpose**: Execute movement action
- **Fields**:
  - `message_id`: Unique identifier
  - `action`: Movement action type
  - `params`: Action-specific parameters
  - See contract for detailed action types and params

### `movement/status`
- **Publisher**: Movement Service
- **Subscribers**: LLM Worker, UI
- **QoS**: 0 (status updates are streaming)
- **Retained**: No
- **Contract**: `MovementStatusUpdate` from `tars.contracts.v1.movement`
- **Purpose**: Movement execution status
- **Fields**:
  - `message_id`: Correlates with command
  - `status`: "started" | "in_progress" | "completed" | "failed"
  - `progress`: Progress percentage (optional)
  - `error`: Error message (if failed)

### `movement/stop`
- **Publisher**: User, Safety systems
- **Subscribers**: Movement Service
- **QoS**: 1 (emergency stop requires reliable delivery)
- **Retained**: No
- **Contract**: `EmergencyStopCommand` from `tars.contracts.v1.movement`
- **Purpose**: Emergency stop all movement
- **Fields**:
  - `message_id`: Unique identifier
  - `reason`: Stop reason

---

## System Domain

### `system/character/current`
- **Publisher**: Memory Worker
- **Subscribers**: LLM Worker, UI
- **QoS**: 1
- **Retained**: Yes (current character state persists)
- **Contract**: `CharacterSnapshot` from `tars.contracts.v1.memory`
- **Purpose**: Current character/persona definition
- **Fields**:
  - `message_id`: Unique identifier
  - `character`: Character data with sections (personality, background, etc.)
  - `ts`: Last update timestamp

### `system/health/<service>`
- **Publisher**: All services
- **Subscribers**: Monitoring, UI
- **QoS**: 1
- **Retained**: Yes (health state persists across disconnects)
- **Contract**: `HealthPing` from `tars.contracts.v1.health`
- **Purpose**: Service health status
- **Topics**:
  - `system/health/stt`
  - `system/health/tts`
  - `system/health/llm`
  - `system/health/memory`
  - `system/health/router`
  - `system/health/wake`
  - `system/health/camera`
  - `system/health/movement`
- **Fields**:
  - `message_id`: Unique identifier
  - `ok`: Health status (true/false)
  - `event`: Status event ("ready", "error", "shutdown")
  - `err`: Error details (if ok=false)
  - `ts`: Timestamp

---

## QoS Level Standards

Per constitutional guidelines:

- **QoS 0 (At most once)**: Streaming data, status updates, partial results
  - `stt/partial`, `stt/audio_fft`, `tts/status`, `llm/stream`, `camera/frame`, `movement/status`
  
- **QoS 1 (At least once)**: Commands, requests, responses, final results
  - `stt/final`, `tts/say`, `tts/control`, `llm/request`, `llm/response`, `llm/cancel`
  - `llm/tool.call.request`, `llm/tool.call.result`, `memory/query`, `memory/results`
  - `wake/event`, `wake/mic`, `camera/capture`, `camera/image`
  - `movement/command`, `movement/stop`, `system/health/*`, `system/character/current`

- **QoS 2 (Exactly once)**: Not currently used (overhead not justified)

---

## Retained Topics

Only these topics use the `retain` flag:

- `system/health/*` - Health status persists for late subscribers
- `system/character/current` - Character state persists
- `llm/tools/registry` - Available tools persist

All other topics are transient (not retained).

---

## Correlation Patterns

### Message Correlation
All contracts include a `message_id` field (auto-generated UUID) for message tracking.

### Request-Response Correlation
- **LLM**: `LLMRequest.id` → `LLMResponse.id` / `LLMStreamDelta.id`
- **Camera**: `CameraCaptureRequest.message_id` → `CameraImageResponse.message_id`
- **Memory**: `MemoryQuery.message_id` → `MemoryResults.message_id`
- **Tools**: `ToolCallRequest.call_id` → `ToolCallResult.call_id`

### Utterance Correlation
`utt_id` field used across services to track end-to-end voice flows:
- STT publishes with `utt_id`
- Router forwards `utt_id` to LLM
- LLM includes `utt_id` in streaming responses
- Router sends `utt_id` to TTS
- TTS status includes `utt_id`

---

## Breaking Change Policy

See `/specs/003-standardize-mqtt-topics/breaking-changes.md` for versioning and migration strategy.

---

## Migration Guide

See `/specs/003-standardize-mqtt-topics/migration-guide.md` for guidance on adopting these standards in new services.
