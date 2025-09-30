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

## Usage

```bash
# Run locally
python main.py

# View MJPEG stream
curl http://localhost:8080/stream

# Get snapshot
curl http://localhost:8080/snapshot > snapshot.jpg

# Run with Docker
docker build -t tars-camera-service .
docker run --device /dev/video0 -p 8080:8080 tars-camera-service
```