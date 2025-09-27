# TARS UI Web

A lightweight WebSocket-powered debug UI for monitoring TARS services. The interface offers pop-out drawers to inspect key data streams:

- **Microphone** – live audio spectrum and partial/final STT transcripts.
- **Memory** – query the memory worker and review the latest retrieval results.
- **MQTT Stream** – real-time view of MQTT events flowing through the system with JSON payload introspection and a clearable history buffer.

## Running

```bash
# from repo root
cd apps/ui-web
pip install -r requirements.txt
python server.py
```

Then open <http://localhost:8080> in your browser. The UI connects to the same MQTT broker as the backend services via the WebSocket bridge exposed by `server.py`.

## Tips

- The MQTT stream drawer retains the most recent 200 messages. Use the **Clear** button to reset the log while monitoring.
- Drawer state is keyboard-accessible; press `Esc` to close the currently open drawer.
- The page is designed for debugging and observability. It does not attempt to send messages back over MQTT—use it alongside the core apps in this repo.
