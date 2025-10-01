"""
ESP32 firmware for driving the TARS servos through a PCA9685 board.

The script runs under MicroPython and turns MQTT `movement/frame` messages into
absolute PWM signals. Frames are produced by the host-side movement-service and
contain calibrated pulse counts, so the firmware only needs to stream those values
to the hardware.
"""

try:
    import ujson as json  # type: ignore
except ImportError:  # pragma: no cover
    import json

try:
    import utime as time  # type: ignore
except ImportError:  # pragma: no cover
    import time

try:
    from machine import I2C, Pin  # type: ignore
except ImportError:  # pragma: no cover
    I2C = None  # type: ignore
    Pin = None  # type: ignore

try:
    import network  # type: ignore
except ImportError:  # pragma: no cover
    network = None  # type: ignore

try:
    from umqtt.robust import MQTTClient  # type: ignore
except ImportError:  # pragma: no cover
    MQTTClient = None  # type: ignore

try:  # pragma: no cover - CPython shim
    import usocket as socket  # type: ignore
except ImportError:  # pragma: no cover
    import socket  # type: ignore

try:  # pragma: no cover - CPython shim
    import machine  # type: ignore
except ImportError:  # pragma: no cover
    machine = None  # type: ignore


def sleep_ms(duration):
    try:
        time.sleep_ms(int(duration))
    except AttributeError:  # pragma: no cover
        time.sleep(duration / 1000.0)


def ticks_ms():
    try:
        return time.ticks_ms()
    except AttributeError:  # pragma: no cover
        return int(time.time() * 1000)


def ticks_diff(a, b):
    try:
        return time.ticks_diff(a, b)
    except AttributeError:  # pragma: no cover
        return a - b


def _open_file(path, mode):
    try:
        return open(path, mode, encoding="utf-8")  # type: ignore
    except (TypeError, ValueError):  # pragma: no cover - MicroPython fallback
        return open(path, mode)  # type: ignore


def save_config(path, config):
    try:
        with _open_file(path, "w") as fp:  # type: ignore
            fp.write(json.dumps(config))
    except OSError:
        pass


class SetupHTTPServer:
    def __init__(self, controller, port):
        self._controller = controller
        self._port = port
        self.port = port
        self._sock = None
        self._start_socket()

    def _start_socket(self):
        try:
            addr = socket.getaddrinfo("0.0.0.0", self._port)[0][-1]
            sock = socket.socket()
            try:
                sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            except AttributeError:  # pragma: no cover
                pass
            sock.bind(addr)
            sock.listen(2)
            try:
                sock.settimeout(0)
            except AttributeError:  # pragma: no cover
                pass
            self._sock = sock
        except Exception:  # pragma: no cover
            if "sock" in locals():
                try:
                    sock.close()
                except Exception:
                    pass
            self._sock = None

    def poll(self):
        if self._sock is None:
            return
        try:
            client, _ = self._sock.accept()
        except OSError:
            return
        except Exception:  # pragma: no cover
            return
        self._handle_client(client)

    def _handle_client(self, client):
        if client is None:
            return
        try:
            try:
                client.settimeout(2)
            except AttributeError:  # pragma: no cover
                pass
            method, path, headers, body = self._controller._read_http_request(client)
            if method is None:
                return
            status, response, _ = self._controller._handle_http_request(
                method,
                path,
                headers,
                body,
                include_controls=True,
                trigger_reset=True,
            )
            self._controller._send_http_response(client, status, response)
        finally:
            try:
                client.close()
            except Exception:
                pass

    def close(self):
        if self._sock is None:
            return
        try:
            self._sock.close()
        except Exception:
            pass
        self._sock = None


_MODE1 = 0x00
_PRESCALE = 0xFE
_LED0_ON_L = 0x06


class PCA9685:
    def __init__(self, i2c, address=0x40):
        self._i2c = i2c
        self._address = address
        self._buffer = bytearray(4)
        self.reset()

    def reset(self):
        self._write_reg(_MODE1, 0x00)
        sleep_ms(10)

    def set_pwm_freq(self, freq_hz):
        prescale_val = int((25_000_000 / (4096 * freq_hz)) - 1)
        current_mode = self._read_reg(_MODE1)
        self._write_reg(_MODE1, (current_mode & 0x7F) | 0x10)
        self._write_reg(_PRESCALE, prescale_val)
        self._write_reg(_MODE1, current_mode)
        sleep_ms(5)
        self._write_reg(_MODE1, current_mode | 0xA1)

    def set_pwm(self, channel, on, off):
        base = _LED0_ON_L + 4 * channel
        self._buffer[0] = on & 0xFF
        self._buffer[1] = (on >> 8) & 0x0F
        self._buffer[2] = off & 0xFF
        self._buffer[3] = (off >> 8) & 0x0F
        self._i2c.writeto_mem(self._address, base, self._buffer)

    def set_off(self, channel):
        self.set_pwm(channel, 0, 0)

    def all_off(self):
        for ch in range(16):
            self.set_off(ch)

    def _write_reg(self, reg, value):
        self._i2c.writeto_mem(self._address, reg, bytes([value & 0xFF]))

    def _read_reg(self, reg):
        data = self._i2c.readfrom_mem(self._address, reg, 1)
        return data[0]


DEFAULT_CONFIG = {
    "wifi": {
        "ssid": "",
        "password": "",
    },
    "mqtt": {
        "host": "192.168.1.10",
        "port": 1883,
        "username": None,
        "password": None,
        "client_id": "tars-esp32",
        "keepalive": 30,
    },
    "pca9685": {
        "address": 0x40,
        "frequency": 50,
        "scl": 22,
        "sda": 21,
    },
    "topics": {
        "frame": "movement/frame",
        "state": "movement/state",
        "health": "system/health/movement-esp32",
    },
    "frame_timeout_ms": 2500,
    "status_led": None,
    "servo_channel_count": 16,
    "servo_centers": {},
    "default_center_pulse": 307,
    "setup_portal": {
        "ssid": "TARS-Setup",
        "password": None,
        "port": 80,
        "timeout_s": 300,
    },
    "config_path": "movement_config.json",
}


def load_config(path):
    try:
        with _open_file(path, "r") as fp:  # type: ignore
            user_cfg = json.loads(fp.read())
    except (OSError, ValueError):
        user_cfg = {}

    merged = json.loads(json.dumps(DEFAULT_CONFIG))
    _deep_update(merged, user_cfg)
    return merged


def _deep_update(target, updates):
    for key, value in updates.items():
        if isinstance(value, dict) and isinstance(target.get(key), dict):
            _deep_update(target[key], value)
        else:
            target[key] = value


class MovementController:
    def __init__(self, config):
        self.config = config
        self._config_path = config.get("config_path", DEFAULT_CONFIG["config_path"])
        self._client = None
        self._pwm = None
        self._station = None
        self._http_server = None
        self._pending_reset_at = None
        self._last_frame_at = ticks_ms()
        self._led_toggle_at = ticks_ms()
        self._positions = {}
        led_pin = config.get("status_led")
        if Pin is not None and led_pin is not None:
            self._led = Pin(led_pin, Pin.OUT)
        else:
            self._led = None

    def _ensure_http_server(self):
        if network is None:
            return
        portal_cfg = self.config.get("setup_portal", {})
        port = int(portal_cfg.get("port", 80))
        if self._http_server is not None and self._http_server.port != port:
            self._http_server.close()
            self._http_server = None
        if self._http_server is None:
            self._http_server = SetupHTTPServer(self, port)

    def _teardown_http_server(self):
        if self._http_server is None:
            return
        self._http_server.close()
        self._http_server = None

    def connect_wifi(self):
        if network is None:
            return
        station = network.WLAN(network.STA_IF)
        station.active(True)

        while True:
            wifi_cfg = self.config.get("wifi", {})
            ssid = (wifi_cfg.get("ssid") or "").strip()
            password = wifi_cfg.get("password")
            if not ssid:
                if not self._start_config_portal():
                    raise RuntimeError("Wi-Fi credentials not provided")
                station.active(True)
                continue

            if station.isconnected():
                break

            try:
                if password:
                    station.connect(ssid, password)
                else:
                    station.connect(ssid)
            except Exception:
                pass

            retries = 0
            while not station.isconnected() and retries < 100:
                sleep_ms(200)
                retries += 1

            if station.isconnected():
                break

            try:
                station.disconnect()
            except Exception:
                pass

            if not self._start_config_portal():
                raise RuntimeError("Wi-Fi connection timeout")
            station.active(True)

        self._station = station
        self._ensure_http_server()

    def setup_pwm(self):
        bus_cfg = self.config["pca9685"]
        if I2C is None or Pin is None:
            raise RuntimeError("PCA9685 requires machine.I2C")
        i2c = I2C(0, scl=Pin(bus_cfg["scl"]), sda=Pin(bus_cfg["sda"]))  # type: ignore
        pwm = PCA9685(i2c, address=bus_cfg.get("address", 0x40))
        pwm.set_pwm_freq(bus_cfg.get("frequency", 50))
        pwm.all_off()
        self._pwm = pwm

    def connect_mqtt(self):
        if MQTTClient is None:
            raise RuntimeError("umqtt.robust is required")
        mqtt_cfg = self.config["mqtt"]
        client = MQTTClient(
            client_id=mqtt_cfg.get("client_id", "tars-esp32"),
            server=mqtt_cfg.get("host"),
            port=mqtt_cfg.get("port", 1883),
            user=mqtt_cfg.get("username"),
            password=mqtt_cfg.get("password"),
            keepalive=mqtt_cfg.get("keepalive", 30),
        )
        client.set_callback(self._on_message)
        client.connect()
        client.subscribe(self.config["topics"]["frame"], qos=1)
        self._client = client
        self._publish_state("ready", {"event": "firmware_online"})
        self._publish_health(True, "ready")

    def loop(self):
        if self._client is None:
            raise RuntimeError("MQTT client not connected")
        timeout_ms = self.config.get("frame_timeout_ms", 2500)
        while True:
            self._service_http()
            if self._led is not None:
                now = ticks_ms()
                if ticks_diff(now, self._led_toggle_at) >= 500:
                    self._led.value(0 if self._led.value() else 1)
                    self._led_toggle_at = now
            try:
                self._client.wait_msg()
            except Exception as exc:  # pragma: no cover
                self._publish_state("error", {"error": "mqtt_wait_failed", "detail": str(exc)})
                self._publish_health(False, "mqtt_wait_failed")
                sleep_ms(500)
                self._client.reconnect()
                self._client.subscribe(self.config["topics"]["frame"], qos=1)
                self._publish_health(True, "reconnected")
            now_ms = ticks_ms()
            if ticks_diff(now_ms, self._last_frame_at) > timeout_ms:
                self._publish_state("error", {"error": "frame_timeout"})
                self._publish_health(False, "frame_timeout")
                self._last_frame_at = now_ms

    def _service_http(self):
        if self._pending_reset_at is not None and ticks_diff(ticks_ms(), self._pending_reset_at) >= 0:
            pending = self._pending_reset_at
            self._pending_reset_at = None
            if machine is not None:
                machine.reset()
            else:  # pragma: no cover
                raise SystemExit
        if self._http_server is not None:
            self._http_server.poll()

    def _on_message(self, topic, payload):
        frame_topic = self.config["topics"]["frame"].encode("utf-8")
        if topic != frame_topic:
            return
        try:
            frame = json.loads(payload.decode("utf-8"))
            self._apply_frame(frame)
        except Exception as exc:  # pragma: no cover
            self._publish_state("error", {"error": "frame_parse_failed", "detail": str(exc)})
            self._publish_health(False, "frame_parse_failed")

    def _apply_frame(self, frame):
        if self._pwm is None or self._client is None:
            return
        channels = frame.get("channels", {})
        for channel_str, target in channels.items():
            channel = int(channel_str)
            self._pwm.set_pwm(channel, 0, int(target))
            self._positions[channel] = int(target)
        hold_ms = int(frame.get("hold_ms") or 0)
        duration_ms = int(frame.get("duration_ms") or 0)
        total_wait = hold_ms + duration_ms
        if total_wait > 0:
            sleep_ms(total_wait)
        if frame.get("disable_after"):
            self._pwm.all_off()
        self._last_frame_at = ticks_ms()
        self._publish_state(
            "frame_ack",
            {
                "id": frame.get("id"),
                "seq": frame.get("seq"),
                "total": frame.get("total"),
            },
        )
        if frame.get("done"):
            self._publish_state("completed", {"id": frame.get("id")})
            self._publish_health(True, "completed")

    def _start_config_portal(self):
        if network is None:
            return False

        self._teardown_http_server()
        portal_cfg = self.config.get("setup_portal", {})
        ap_ssid = portal_cfg.get("ssid") or "TARS-Setup"
        ap_password = portal_cfg.get("password") or ""
        ap_port = int(portal_cfg.get("port", 80))
        timeout_s = int(portal_cfg.get("timeout_s", 300) or 0)

        station = network.WLAN(network.STA_IF)
        station.active(False)

        ap = network.WLAN(network.AP_IF)
        ap.active(True)
        try:
            if ap_password and len(ap_password) >= 8:
                ap.config(essid=ap_ssid, password=ap_password)
            else:
                ap.config(essid=ap_ssid, authmode=network.AUTH_OPEN)
        except Exception:  # pragma: no cover - some ports lack auth constants
            ap.config(essid=ap_ssid)

        addr = socket.getaddrinfo("0.0.0.0", ap_port)[0][-1]
        sock = socket.socket()
        try:
            sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        except AttributeError:  # pragma: no cover - MicroPython subsets
            pass
        sock.bind(addr)
        sock.listen(1)
        try:
            sock.settimeout(1)
        except AttributeError:  # pragma: no cover
            pass

        deadline = None
        if timeout_s > 0:
            deadline = ticks_ms() + timeout_s * 1000

        updated = False

        try:
            while True:
                if deadline is not None and ticks_diff(ticks_ms(), deadline) >= 0:
                    break
                try:
                    client, _ = sock.accept()
                except OSError:
                    continue

                status, response, result = ("200 OK", "", None)
                try:
                    method, path, headers, body = self._read_http_request(client)
                    if method is not None:
                        status, response, result = self._handle_http_request(
                            method,
                            path,
                            headers,
                            body,
                            include_controls=False,
                            trigger_reset=False,
                        )
                finally:
                    try:
                        self._send_http_response(client, status, response)
                    except Exception:
                        pass
                    try:
                        client.close()
                    except Exception:
                        pass

                if result == "wifi_updated":
                    updated = True
                    break
        finally:
            try:
                sock.close()
            except Exception:
                pass
            ap.active(False)
            station.active(True)

        if updated:
            sleep_ms(500)
        return updated

    def _render_form_page(self, error=None, message=None, include_controls=False):
        wifi_cfg = self.config.get("wifi", {})
        ssid_value = self._escape_html(wifi_cfg.get("ssid", ""))
        parts = [
            "<!DOCTYPE html><html><head><meta charset='utf-8'>",
            "<meta name='viewport' content='width=device-width,initial-scale=1'>",
            "<title>TARS Wi-Fi Setup</title>",
            "<style>body{font-family:Arial,Helvetica,sans-serif;padding:24px;",
            "background:#101820;color:#f2f2f2;}label{display:block;margin-top:16px;}",
            "input{width:100%;padding:10px;margin-top:6px;border-radius:4px;border:1px solid #444;}",
            "button{margin-top:24px;padding:12px 18px;background:#ff6f3c;color:#101820;",
            "border:none;border-radius:4px;font-size:16px;}",
            ".grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(140px,1fr));",
            "gap:12px;margin-top:16px;}",
            ".card{background:#1a2733;padding:12px;border-radius:6px;text-align:center;}",
            ".card button{width:100%;margin:0;margin-top:8px;}",
            "section.center{margin-top:32px;}",
            "p.meta{margin-top:16px;color:#b7c9e2;font-size:14px;}",
            "button.wide{width:100%;}",
            "</style></head><body>",
            "<h1>TARS Wi-Fi Setup</h1>",
            "<p>Connect this ESP32 to your home network by entering the Wi-Fi credentials below.</p>",
        ]

        if error:
            parts.append("<p style='color:#d33;'>%s</p>" % self._escape_html(error))
        if message:
            parts.append("<p style='color:#4caf50;'>%s</p>" % self._escape_html(message))

        parts.extend(
            [
                "<form method='POST'>",
                f"<label>Wi-Fi SSID<input name='ssid' value='{ssid_value}' maxlength='64' required></label>",
                "<label>Password<input name='password' type='password' maxlength='64'></label>",
                "<button type='submit'>Save &amp; Connect</button>",
                "</form>",
            ]
        )

        if include_controls:
            portal_cfg = self.config.get("setup_portal", {})
            port = int(portal_cfg.get("port", 80))
            parts.append(
                f"<p class='meta'>HTTP portal active on port {port}."
                f" Default center pulse: {self._escape_html(str(self.config.get('default_center_pulse', 307)))}.</p>"
            )
            controls_html = self._build_center_controls()
            if controls_html:
                parts.append(controls_html)

        parts.append("</body></html>")
        return "".join(parts)

    def _build_center_controls(self):
        channels = int(self.config.get("servo_channel_count", 0) or 0)
        if channels <= 0 or self._pwm is None:
            return ""
        buttons = []
        for idx in range(channels):
            buttons.append(
                "<div class='card'><h3>Channel %d</h3>"
                "<form method='POST'>"
                "<input type='hidden' name='center' value='%d'>"
                "<button type='submit'>Center</button>"
                "</form></div>" % (idx, idx)
            )
        controls = ["<section class='center'>", "<h2>Servo Centering</h2>", "<div class='grid'>"]
        controls.extend(buttons)
        controls.append("</div>")
        controls.append(
            "<form method='POST'>"
            "<input type='hidden' name='center_all' value='1'>"
            "<button type='submit' class='wide'>Center All</button>"
            "</form>"
        )
        controls.append("</section>")
        return "".join(controls)

    def _read_http_request(self, client):
        data = b""
        while True:
            try:
                chunk = client.recv(512)
            except Exception:
                chunk = b""
            if not chunk:
                break
            data += chunk
            if b"\r\n\r\n" in data and len(chunk) < 512:
                break
        if not data:
            return None, "/", {}, ""

        if b"\r\n\r\n" in data:
            header_bytes, body_bytes = data.split(b"\r\n\r\n", 1)
        else:
            header_bytes, body_bytes = data, b""

        lines = header_bytes.split(b"\r\n")
        if not lines:
            return None, "/", {}, ""
        request_line = lines[0]
        parts = request_line.split()
        if len(parts) < 2:
            return None, "/", {}, ""
        method = parts[0].decode("utf-8", "ignore")
        path = parts[1].decode("utf-8", "ignore")

        headers = {}
        content_length = 0
        for line in lines[1:]:
            if b":" not in line:
                continue
            key, value = line.split(b":", 1)
            key_decoded = key.decode("utf-8", "ignore").strip().lower()
            value_decoded = value.decode("utf-8", "ignore").strip()
            headers[key_decoded] = value_decoded
            if key_decoded == "content-length":
                try:
                    content_length = int(value_decoded)
                except ValueError:
                    content_length = 0

        while len(body_bytes) < content_length:
            try:
                chunk = client.recv(512)
            except Exception:
                chunk = b""
            if not chunk:
                break
            body_bytes += chunk

        body = body_bytes.decode("utf-8", "ignore")
        return method, path, headers, body

    def _send_http_response(self, client, status, body):
        if body is None:
            body = ""
        payload = body if isinstance(body, str) else str(body)
        try:
            body_bytes = payload.encode("utf-8")
        except Exception:  # pragma: no cover
            body_bytes = payload
        header = (
            f"HTTP/1.1 {status}\r\n"
            "Content-Type: text/html; charset=utf-8\r\n"
            f"Content-Length: {len(body_bytes)}\r\n"
            "Connection: close\r\n\r\n"
        ).encode("utf-8")
        client.send(header)
        if body_bytes:
            client.send(body_bytes)

    def _handle_http_request(
        self,
        method,
        path,
        headers,
        body,
        include_controls,
        trigger_reset,
    ):
        if path not in ("/", ""):
            return "404 Not Found", "<h1>Not Found</h1>", None

        if method == "POST":
            form = self._parse_form(body or "")
            if "ssid" in form:
                ssid_val = form.get("ssid", "").strip()
                password_val = form.get("password", "")
                if not ssid_val:
                    html = self._render_form_page(
                        error="SSID is required",
                        include_controls=include_controls,
                    )
                    return "200 OK", html, None
                self.config.setdefault("wifi", {})
                self.config["wifi"]["ssid"] = ssid_val
                self.config["wifi"]["password"] = password_val
                save_config(self._config_path, self.config)
                if trigger_reset:
                    self._pending_reset_at = ticks_ms() + 1500
                return "200 OK", self._render_success_page(ssid_val), "wifi_updated"

            if include_controls:
                if "center_all" in form:
                    count = self._center_all_servos()
                    if count:
                        html = self._render_form_page(
                            message=f"Centered {count} channels.",
                            include_controls=True,
                        )
                    else:
                        html = self._render_form_page(
                            error="Unable to center servos — hardware not ready.",
                            include_controls=True,
                        )
                    return "200 OK", html, None
                if "center" in form:
                    channel_raw = form.get("center", "")
                    try:
                        channel = int(channel_raw)
                    except ValueError:
                        channel = -1
                    success = self._center_servo(channel)
                    if success:
                        html = self._render_form_page(
                            message=f"Centered channel {channel}.",
                            include_controls=True,
                        )
                    else:
                        html = self._render_form_page(
                            error="Invalid channel or hardware not ready.",
                            include_controls=True,
                        )
                    return "200 OK", html, None

        html = self._render_form_page(include_controls=include_controls)
        return "200 OK", html, None

    def _center_servo(self, channel):
        if self._pwm is None or channel < 0:
            return False
        max_channels = int(self.config.get("servo_channel_count", 16) or 16)
        if channel >= max_channels:
            return False
        centers = self.config.get("servo_centers", {})
        value = None
        if isinstance(centers, dict):
            if channel in centers:
                value = centers[channel]
            elif str(channel) in centers:
                value = centers[str(channel)]
        if value is None:
            value = self.config.get("default_center_pulse", DEFAULT_CONFIG.get("default_center_pulse", 307))
        try:
            value_int = int(value)
        except (TypeError, ValueError):
            value_int = int(DEFAULT_CONFIG.get("default_center_pulse", 307))
        try:
            self._pwm.set_pwm(channel, 0, value_int)
        except Exception:
            return False
        self._positions[channel] = value_int
        return True

    def _center_all_servos(self):
        max_channels = int(self.config.get("servo_channel_count", 16) or 16)
        success_count = 0
        for idx in range(max_channels):
            if self._center_servo(idx):
                success_count += 1
        return success_count

    def _render_success_page(self, ssid):
        ssid_html = self._escape_html(ssid)
        return (
            "<!DOCTYPE html><html><head><meta charset='utf-8'>"
            "<meta name='viewport' content='width=device-width,initial-scale=1'>"
            "<title>Credentials Saved</title>"
            "<style>body{font-family:Arial,Helvetica,sans-serif;padding:24px;"
            "background:#101820;color:#f2f2f2;}a{color:#ff6f3c;}</style></head><body>"
            "<h1>Credentials saved</h1>"
            f"<p>The ESP32 will now reboot and try to join <strong>{ssid_html}</strong>.</p>"
            "<p>You can disconnect from the setup Wi-Fi network.</p>"
            "</body></html>"
        )

    def _parse_form(self, body):
        data = {}
        if not body:
            return data
        for pair in body.split("&"):
            if "=" not in pair:
                continue
            key, value = pair.split("=", 1)
            data[self._url_decode(key)] = self._url_decode(value)
        return data

    @staticmethod
    def _url_decode(value):
        value = value.replace("+", " ")
        result = []
        i = 0
        length = len(value)
        while i < length:
            if value[i] == "%" and i + 2 < length:
                try:
                    result.append(chr(int(value[i + 1 : i + 3], 16)))
                    i += 3
                    continue
                except ValueError:
                    pass
            result.append(value[i])
            i += 1
        return "".join(result)

    @staticmethod
    def _escape_html(value):
        replacements = {
            "&": "&amp;",
            "<": "&lt;",
            ">": "&gt;",
            '"': "&quot;",
            "'": "&#x27;",
        }
        out = []
        for char in value:
            out.append(replacements.get(char, char))
        return "".join(out)

    def _publish_state(self, event, payload):
        if self._client is None:
            return
        body = {
            "event": event,
            "timestamp": time.time(),
        }
        if payload:
            body.update(payload)
        state_topic = self.config["topics"]["state"]
        retain = event == "ready"
        self._client.publish(state_topic, json.dumps(body), qos=1, retain=retain)

    def _publish_health(self, ok, event):
        if self._client is None:
            return
        topic = self.config["topics"].get("health")
        if not topic:
            return
        body = {
            "ok": bool(ok),
            "event": event,
            "timestamp": time.time(),
        }
        self._client.publish(topic, json.dumps(body), qos=1, retain=True)


def main():  # pragma: no cover
    config = load_config(DEFAULT_CONFIG["config_path"])
    controller = MovementController(config)
    controller.connect_wifi()
    controller.setup_pwm()
    controller.connect_mqtt()
    controller.loop()


if __name__ == "__main__":  # pragma: no cover
    main()
