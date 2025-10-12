"""
MQTT Monitor - Real-time MQTT message monitoring web interface

This module provides a web interface for monitoring MQTT messages on the ESP32:
- Shows recent incoming messages (topic, payload, timestamp)
- Shows recent outgoing messages (published messages)
- Auto-refreshing page with message history
- Useful for debugging and monitoring MQTT communication

Usage:
    monitor = MQTTMonitor(port=8080, max_messages=50)
    monitor.log_incoming("movement/test", b'{"command":"wave"}')
    monitor.log_outgoing("movement/status", b'{"status":"executing"}')
    
    # In main loop:
    monitor.poll()
"""

try:
    import socket
    import ujson as json
    import utime as time
except ImportError:
    socket = None
    import json
    import time


class MQTTMonitor:
    """
    HTTP server for monitoring MQTT message traffic.
    
    Provides a web interface showing:
    - Recent incoming MQTT messages
    - Recent outgoing MQTT messages
    - Timestamps and payload preview
    - Connection status
    
    Args:
        port: HTTP port for monitor interface (default 8080)
        max_messages: Maximum messages to keep in history (default 50)
    """
    
    def __init__(self, port=8080, max_messages=50):
        self.port = port
        self.max_messages = max_messages
        self._sock = None
        self._incoming = []  # List of (timestamp, topic, payload, size)
        self._outgoing = []  # List of (timestamp, topic, payload, size)
        self._connected = False
        self._connect_time = None
        self._start_socket()
    
    def _start_socket(self):
        """Start the HTTP server socket."""
        if socket is None:
            return
            
        try:
            addr = socket.getaddrinfo("0.0.0.0", self.port)[0][-1]
            sock = socket.socket()
            try:
                sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            except AttributeError:
                pass
            sock.bind(addr)
            sock.listen(2)
            try:
                sock.settimeout(0)
            except AttributeError:
                try:
                    sock.setblocking(False)
                except Exception:
                    pass
            self._sock = sock
            print(f"✓ MQTT Monitor started on port {self.port}")
        except Exception as e:
            print(f"✗ MQTT Monitor socket error: {e}")
            if "sock" in locals():
                try:
                    sock.close()
                except Exception:
                    pass
            self._sock = None
    
    def set_connected(self, connected):
        """Update MQTT connection status."""
        self._connected = connected
        if connected and self._connect_time is None:
            self._connect_time = time.time()
    
    def log_incoming(self, topic, payload):
        """
        Log an incoming MQTT message.
        
        Args:
            topic: MQTT topic (str or bytes)
            payload: Message payload (str or bytes)
        """
        try:
            topic_str = topic.decode('utf-8') if isinstance(topic, bytes) else str(topic)
            payload_str = payload.decode('utf-8') if isinstance(payload, bytes) else str(payload)
            size = len(payload) if isinstance(payload, bytes) else len(payload_str.encode('utf-8'))
            
            self._incoming.append((time.time(), topic_str, payload_str, size))
            
            # Trim to max_messages
            if len(self._incoming) > self.max_messages:
                self._incoming = self._incoming[-self.max_messages:]
        except Exception as e:
            print(f"Error logging incoming message: {e}")
    
    def log_outgoing(self, topic, payload):
        """
        Log an outgoing MQTT message.
        
        Args:
            topic: MQTT topic (str or bytes)
            payload: Message payload (str or bytes)
        """
        try:
            topic_str = topic.decode('utf-8') if isinstance(topic, bytes) else str(topic)
            payload_str = payload.decode('utf-8') if isinstance(payload, bytes) else str(payload)
            size = len(payload) if isinstance(payload, bytes) else len(payload_str.encode('utf-8'))
            
            self._outgoing.append((time.time(), topic_str, payload_str, size))
            
            # Trim to max_messages
            if len(self._outgoing) > self.max_messages:
                self._outgoing = self._outgoing[-self.max_messages:]
        except Exception as e:
            print(f"Error logging outgoing message: {e}")
    
    def poll(self):
        """Poll for incoming HTTP connections (non-blocking)."""
        if self._sock is None:
            return
        
        try:
            client, addr = self._sock.accept()
        except OSError:
            return
        except Exception:
            return
        
        self._handle_client(client)
    
    def _handle_client(self, client):
        """Handle an accepted HTTP client connection."""
        if client is None:
            return
        
        try:
            try:
                client.settimeout(2)
            except AttributeError:
                pass
            
            # Read request
            request_line = self._read_request_line(client)
            if request_line is None:
                return
            
            method, path = request_line
            
            # Handle routes
            if path == "/" or path == "":
                html = self._render_monitor_page()
                self._send_response(client, "200 OK", html)
            elif path == "/api/messages":
                json_data = self._get_messages_json()
                self._send_json_response(client, "200 OK", json_data)
            elif path == "/clear":
                self._incoming = []
                self._outgoing = []
                html = self._render_monitor_page(message="Message history cleared")
                self._send_response(client, "200 OK", html)
            else:
                self._send_response(client, "404 Not Found", "<h1>Not Found</h1>")
        finally:
            try:
                client.close()
            except Exception:
                pass
    
    def _read_request_line(self, client):
        """Read and parse HTTP request line."""
        try:
            data = client.recv(512)
            if not data:
                return None
            
            lines = data.split(b"\r\n")
            if not lines:
                return None
            
            request_line = lines[0]
            parts = request_line.split()
            if len(parts) < 2:
                return None
            
            method = parts[0].decode("utf-8", "ignore")
            path = parts[1].decode("utf-8", "ignore")
            return method, path
        except Exception:
            return None
    
    def _send_response(self, client, status, body):
        """Send HTTP response."""
        try:
            body_bytes = body.encode("utf-8") if isinstance(body, str) else body
            header = (
                f"HTTP/1.1 {status}\r\n"
                "Content-Type: text/html; charset=utf-8\r\n"
                f"Content-Length: {len(body_bytes)}\r\n"
                "Connection: close\r\n\r\n"
            ).encode("utf-8")
            client.send(header)
            client.send(body_bytes)
        except Exception:
            pass
    
    def _send_json_response(self, client, status, data):
        """Send JSON response."""
        try:
            json_str = json.dumps(data)
            body_bytes = json_str.encode("utf-8")
            header = (
                f"HTTP/1.1 {status}\r\n"
                "Content-Type: application/json; charset=utf-8\r\n"
                f"Content-Length: {len(body_bytes)}\r\n"
                "Connection: close\r\n\r\n"
            ).encode("utf-8")
            client.send(header)
            client.send(body_bytes)
        except Exception:
            pass
    
    def _get_messages_json(self):
        """Get messages as JSON for API endpoint."""
        return {
            "connected": self._connected,
            "uptime": int(time.time() - self._connect_time) if self._connect_time else 0,
            "incoming": [
                {
                    "time": int(t),
                    "topic": topic,
                    "payload": payload[:200],  # Truncate long payloads
                    "size": size
                }
                for t, topic, payload, size in reversed(self._incoming[-20:])
            ],
            "outgoing": [
                {
                    "time": int(t),
                    "topic": topic,
                    "payload": payload[:200],
                    "size": size
                }
                for t, topic, payload, size in reversed(self._outgoing[-20:])
            ]
        }
    
    def _render_monitor_page(self, error=None, message=None):
        """Render the MQTT monitor HTML page."""
        parts = [
            "<!DOCTYPE html><html><head><meta charset='utf-8'>",
            "<meta name='viewport' content='width=device-width,initial-scale=1'>",
            "<title>TARS MQTT Monitor</title>",
            "<style>",
            "body{font-family:'Courier New',monospace;padding:16px;background:#0d1117;color:#c9d1d9;margin:0;}",
            "h1{color:#58a6ff;margin:0 0 8px 0;font-size:24px;}",
            ".header{display:flex;justify-content:space-between;align-items:center;margin-bottom:16px;",
            "padding:16px;background:#161b22;border-radius:6px;}",
            ".status{display:flex;align-items:center;gap:12px;}",
            ".status-dot{width:12px;height:12px;border-radius:50%;",
            "background:#3fb950;animation:pulse 2s infinite;}",
            ".status-dot.disconnected{background:#f85149;animation:none;}",
            "@keyframes pulse{0%,100%{opacity:1;}50%{opacity:0.5;}}",
            "button{padding:8px 16px;background:#238636;color:#fff;border:none;",
            "border-radius:6px;cursor:pointer;font-size:14px;}",
            "button:hover{background:#2ea043;}",
            ".section{margin:16px 0;padding:16px;background:#161b22;border-radius:6px;}",
            ".section h2{color:#58a6ff;margin:0 0 12px 0;font-size:18px;}",
            ".messages{max-height:400px;overflow-y:auto;}",
            ".message{padding:12px;margin:8px 0;background:#0d1117;border-left:3px solid #58a6ff;",
            "border-radius:4px;font-size:13px;}",
            ".message.outgoing{border-left-color:#f78166;}",
            ".message-header{display:flex;justify-content:space-between;margin-bottom:6px;color:#8b949e;}",
            ".topic{color:#58a6ff;font-weight:bold;}",
            ".payload{background:#010409;padding:8px;border-radius:4px;overflow-x:auto;white-space:pre-wrap;",
            "word-break:break-all;color:#c9d1d9;margin-top:6px;}",
            ".empty{color:#8b949e;font-style:italic;text-align:center;padding:24px;}",
            ".stats{display:grid;grid-template-columns:repeat(auto-fit,minmax(150px,1fr));gap:12px;margin-bottom:16px;}",
            ".stat-card{padding:12px;background:#0d1117;border-radius:6px;text-align:center;}",
            ".stat-value{font-size:24px;font-weight:bold;color:#58a6ff;}",
            ".stat-label{font-size:12px;color:#8b949e;margin-top:4px;}",
            "</style>",
            "</head><body>",
        ]
        
        # Header
        status_class = "" if self._connected else " disconnected"
        status_text = "Connected" if self._connected else "Disconnected"
        uptime = int(time.time() - self._connect_time) if self._connect_time else 0
        uptime_str = self._format_uptime(uptime) if self._connected else "N/A"
        
        parts.extend([
            "<div class='header'>",
            "<div><h1>🔌 TARS MQTT Monitor</h1>",
            f"<div style='font-size:12px;color:#8b949e;'>Port {self.port} • Uptime: {uptime_str}</div></div>",
            "<div class='status'>",
            f"<div class='status-dot{status_class}'></div>",
            f"<span>{status_text}</span>",
            "<button onclick='location.reload()'>Refresh</button>",
            "<button onclick='location.href=\"/clear\"'>Clear</button>",
            "</div></div>",
        ])
        
        # Messages/Error
        if error:
            parts.append(f"<div style='background:#f85149;color:#fff;padding:12px;border-radius:6px;margin-bottom:16px;'>{self._escape_html(error)}</div>")
        if message:
            parts.append(f"<div style='background:#3fb950;color:#fff;padding:12px;border-radius:6px;margin-bottom:16px;'>{self._escape_html(message)}</div>")
        
        # Stats
        parts.extend([
            "<div class='stats'>",
            "<div class='stat-card'>",
            f"<div class='stat-value'>{len(self._incoming)}</div>",
            "<div class='stat-label'>Incoming Messages</div>",
            "</div>",
            "<div class='stat-card'>",
            f"<div class='stat-value'>{len(self._outgoing)}</div>",
            "<div class='stat-label'>Outgoing Messages</div>",
            "</div>",
            "<div class='stat-card'>",
            f"<div class='stat-value'>{len(self._incoming) + len(self._outgoing)}</div>",
            "<div class='stat-label'>Total Messages</div>",
            "</div>",
            "</div>",
        ])
        
        # Incoming messages
        parts.append("<div class='section'>")
        parts.append("<h2>📥 Incoming Messages</h2>")
        parts.append("<div class='messages'>")
        
        if self._incoming:
            for timestamp, topic, payload, size in reversed(self._incoming[-20:]):
                time_str = self._format_timestamp(timestamp)
                parts.extend([
                    "<div class='message'>",
                    "<div class='message-header'>",
                    f"<span class='topic'>{self._escape_html(topic)}</span>",
                    f"<span>{time_str} • {size} bytes</span>",
                    "</div>",
                    f"<div class='payload'>{self._escape_html(payload[:500])}</div>",
                    "</div>",
                ])
        else:
            parts.append("<div class='empty'>No incoming messages yet</div>")
        
        parts.append("</div></div>")
        
        # Outgoing messages
        parts.append("<div class='section'>")
        parts.append("<h2>📤 Outgoing Messages</h2>")
        parts.append("<div class='messages'>")
        
        if self._outgoing:
            for timestamp, topic, payload, size in reversed(self._outgoing[-20:]):
                time_str = self._format_timestamp(timestamp)
                parts.extend([
                    "<div class='message outgoing'>",
                    "<div class='message-header'>",
                    f"<span class='topic'>{self._escape_html(topic)}</span>",
                    f"<span>{time_str} • {size} bytes</span>",
                    "</div>",
                    f"<div class='payload'>{self._escape_html(payload[:500])}</div>",
                    "</div>",
                ])
        else:
            parts.append("<div class='empty'>No outgoing messages yet</div>")
        
        parts.append("</div></div>")
        
        # Auto-refresh script
        parts.append(
            "<script>"
            "setTimeout(function(){location.reload();},5000);"
            "</script>"
        )
        
        parts.append("</body></html>")
        return "".join(parts)
    
    def _format_timestamp(self, timestamp):
        """Format timestamp as HH:MM:SS."""
        try:
            t = time.localtime(timestamp)
            return f"{t[3]:02d}:{t[4]:02d}:{t[5]:02d}"
        except Exception:
            return str(int(timestamp))
    
    def _format_uptime(self, seconds):
        """Format uptime as human-readable string."""
        if seconds < 60:
            return f"{seconds}s"
        elif seconds < 3600:
            return f"{seconds // 60}m {seconds % 60}s"
        else:
            hours = seconds // 3600
            mins = (seconds % 3600) // 60
            return f"{hours}h {mins}m"
    
    def _escape_html(self, value):
        """Escape HTML special characters."""
        replacements = {
            "&": "&amp;",
            "<": "&lt;",
            ">": "&gt;",
            '"': "&quot;",
            "'": "&#x27;",
        }
        out = []
        for char in str(value):
            out.append(replacements.get(char, char))
        return "".join(out)
    
    def close(self):
        """Close the HTTP server socket."""
        if self._sock is None:
            return
        try:
            self._sock.close()
        except Exception:
            pass
        self._sock = None


# Self-tests
if __name__ == "__main__":
    print("Running mqtt_monitor self-tests...")
    
    # Test 1: HTML escape
    monitor = MQTTMonitor(port=8080, max_messages=10)
    assert monitor._escape_html("<script>") == "&lt;script&gt;"
    assert monitor._escape_html("A & B") == "A &amp; B"
    print("✓ HTML escape")
    
    # Test 2: Message logging
    monitor.log_incoming("test/topic", b'{"key":"value"}')
    assert len(monitor._incoming) == 1
    assert monitor._incoming[0][1] == "test/topic"
    print("✓ Incoming message logging")
    
    # Test 3: Outgoing logging
    monitor.log_outgoing("status/topic", '{"status":"ok"}')
    assert len(monitor._outgoing) == 1
    assert monitor._outgoing[0][1] == "status/topic"
    print("✓ Outgoing message logging")
    
    # Test 4: Max messages limit
    for i in range(15):
        monitor.log_incoming(f"test/{i}", f"message {i}")
    assert len(monitor._incoming) <= 10
    print("✓ Max messages limit")
    
    # Test 5: Connection status
    monitor.set_connected(True)
    assert monitor._connected is True
    assert monitor._connect_time is not None
    print("✓ Connection status")
    
    # Test 6: JSON API
    data = monitor._get_messages_json()
    assert "connected" in data
    assert "incoming" in data
    assert "outgoing" in data
    print("✓ JSON API")
    
    # Test 7: Render page
    html = monitor._render_monitor_page()
    assert "TARS MQTT Monitor" in html
    assert "Incoming Messages" in html
    assert "Outgoing Messages" in html
    print("✓ Page rendering")
    
    print("\n✓ All mqtt_monitor tests passed!")
