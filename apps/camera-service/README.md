# TARS Camera Service

Camera service that captures video frames and provides MJPEG streaming over HTTP.
Publishes occasional frames to MQTT for monitoring/debugging.
Optimized for mobile robot use cases with configurable resolution, frame rate, and quality settings.

## Configuration

The service supports the following environment variables:

- `MQTT_URL`: MQTT broker URL (default: `mqtt://tars:pass@127.0.0.1:1883`)
- `CAMERA_FRAME_TOPIC`: MQTT topic for occasional monitoring frames (default: `camera/frame`)
- `CAMERA_WIDTH`: Frame width in pixels (default: `640`)
- `CAMERA_HEIGHT`: Frame height in pixels (default: `480`)
- `CAMERA_FPS`: Target frames per second (default: `10`)
- `CAMERA_QUALITY`: JPEG quality (1-100, default: `80`)
- `CAMERA_ROTATION`: Camera rotation in degrees (0, 90, 180, 270, default: `0`)
- `CAMERA_MQTT_RATE`: MQTT publishing rate in seconds (default: `2` - publish every 2 seconds)
- `CAMERA_HTTP_HOST`: HTTP server host (default: `0.0.0.0`)
- `CAMERA_HTTP_PORT`: HTTP server port (default: `8080`)

## Endpoints

- `GET /stream`: MJPEG video stream for live viewing
- `GET /snapshot`: Single JPEG frame snapshot

## MQTT Topics

- `camera/frame`: Publishes occasional JPEG frames as base64-encoded strings (for monitoring)
- `system/health/camera`: Health status (retained)

## Frame Format (MQTT)

Each monitoring frame is published as a JSON payload:

```json
{
  "frame": "base64_encoded_jpeg_data",
  "timestamp": 1640995200.123,
  "width": 640,
  "height": 480,
  "quality": 80,
  "mqtt_rate": 2
}
```

## Installation

### From Source

```bash
cd apps/camera-service
pip install -e .
```

### For Development

```bash
cd apps/camera-service
pip install -e ".[dev]"

# Copy example environment
cp .env.example .env
```

## Usage

### Running the Service

**Standalone:**
```bash
tars-camera-service
```

**With Python module:**
```bash
python -m camera_service
```

**In Docker:**
```bash
docker compose up camera-service
```

### HTTP Endpoints

- `GET /stream`: MJPEG video stream for live viewing
- `GET /snapshot`: Single JPEG frame snapshot

### Viewing the Stream

```bash
# View MJPEG stream in browser
open http://localhost:8080/stream

# Get snapshot
curl http://localhost:8080/snapshot > snapshot.jpg
```

## MQTT Client Architecture

**Centralized Client**: Uses `tars.adapters.mqtt_client.MQTTClient` from `tars-core` package.

**Key Features**:
- **Auto-Reconnection**: Exponential backoff (0.5s-5s configurable) with session recovery
- **Health Monitoring**: Publishes health status to `system/health/camera` (retained)
- **Heartbeat**: Optional keepalive messages to `system/keepalive/camera`
- **Message Deduplication**: TTL cache prevents duplicate processing during reconnects
- **Async Publishing**: Non-blocking frame publishing with automatic retries

**Publishing Pattern**:
```python
async def _publish_frame(self, jpeg_data: bytes, ...) -> None:
    """Publish frame using centralized client."""
    payload = {"frame": base64_encode(jpeg_data), ...}
    await self.mqtt.publish(self.cfg.mqtt.frame_topic, payload, qos=0)
```

**Health Integration**:
- Health check reports camera backend and capture status
- Auto-publishes to `system/health/camera` on connect/disconnect
- Heartbeat maintains session presence

**Migration Benefits** (from local wrapper):
- Eliminated ~100 lines of manual reconnection logic
- Centralized health monitoring across all services
- Consistent error handling and logging patterns
- Async-first design (no thread blocking)

## Development

### Setup Development Environment

```bash
# Install with dev dependencies
pip install -e ".[dev]"

# Copy example environment
cp .env.example .env
```

### Available Make Targets

| Target | Description |
|--------|-------------|
| `make fmt` | Format code with ruff and black |
| `make lint` | Lint with ruff and type-check with mypy |
| `make test` | Run tests with coverage |
| `make check` | Run all checks (CI gate) |
| `make build` | Build Python package |
| `make clean` | Remove build artifacts |
| `make install` | Install in editable mode |
| `make install-dev` | Install with dev dependencies |

### Code Quality

```bash
# Format code
make fmt

# Lint and type-check
make lint

# Run all checks (fmt + lint + test)
make check
```

### Project Structure

```
camera-service/
├── src/
│   └── camera_service/     # Source code
│       ├── __init__.py
│       ├── __main__.py     # CLI entry point
│       ├── config.py       # Configuration parsing
│       ├── service.py      # Core business logic (MQTT lifecycle, async publishing)
│       ├── capture.py      # Camera capture
│       └── streaming.py    # HTTP streaming
├── tests/
│   ├── conftest.py         # Shared fixtures
│   ├── unit/               # Unit tests
│   ├── integration/        # Integration tests
│   └── contract/           # MQTT contract tests
├── Makefile                # Build automation
├── pyproject.toml          # Package configuration
└── README.md               # This file
```

## Testing

```bash
# Run all tests
make test

# Run specific test categories
pytest -m unit
pytest -m integration
pytest -m contract
```

## Architecture

The camera service consists of three main components:

1. **Camera Capture** (`capture.py`): Interfaces with V4L2 camera device, handles frame capture and error recovery
2. **HTTP Streaming** (`streaming.py`): Flask server providing MJPEG stream and snapshot endpoints
3. **Service Orchestration** (`service.py`): Coordinates capture, streaming, and async MQTT publishing

### MQTT Integration

Uses centralized `tars.adapters.mqtt_client.MQTTClient` for all MQTT operations.

#### Subscribed Topics

None - this service only publishes.

#### Published Topics

| Topic | QoS | Retained | Payload Schema | Purpose |
|-------|-----|----------|----------------|---------|
| `camera/frame` | 0 | No | `{ frame: str, timestamp: float, width: int, height: int, quality: int, mqtt_rate: int, backend: str, consecutive_failures: int }` | Monitoring frames (base64 JPEG) |
| `system/health/camera` | 1 | Yes | `{ ok: bool, event?: str, timestamp: float }` | Service health status (auto-published) |
| `system/keepalive/camera` | 0 | No | `{ ok: bool, event: "hb", ts: float }` | Heartbeat (auto-published) |

**Frame Payload Example:**
```json
{
  "frame": "/9j/4AAQSkZJRgABAQAAAQABAAD...",
  "timestamp": 1640995200.123,
  "width": 640,
  "height": 480,
  "quality": 80,
  "mqtt_rate": 2,
  "backend": "opencv",
  "consecutive_failures": 0
}
  "mqtt_rate": 2
}
```

**Health Payload Example (healthy):**
```json
{
  "ok": true,
  "event": "service_started",
  "timestamp": 1640995200.123
}
```

**Health Payload Example (error):**
```json
{
  "ok": false,
  "err": "Camera device not found",
  "timestamp": 1640995200.123
}
```

## Troubleshooting

### Camera Not Found

**Issue**: Service can't open camera device  
**Solution**: 
- Check device exists: `ls -la /dev/video*`
- Verify permissions: Add user to `video` group
- Test camera: `v4l2-ctl --list-devices`

### Import Errors

**Issue**: Can't import package after moving to src/  
**Solution**: Run `pip install -e .` to install in editable mode

### HTTP Port Already in Use

**Issue**: Port 8080 already in use  
**Solution**: Change `CAMERA_HTTP_PORT` environment variable

## Related Services

- **Movement Service** - May consume camera frames for visual navigation
- **UI Services** - Display camera stream in user interfaces