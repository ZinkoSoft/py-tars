"""
WiFi Manager - WiFi connection and setup portal for ESP32

This module handles:
- WiFi connection with retry logic
- Setup portal for WiFi configuration via web interface
- SSID scanning and selection
- HTTP server for setup portal
- LED integration for visual feedback during connection
"""

# Imports with MicroPython/CPython compatibility
try:
    import network  # type: ignore
    import socket  # type: ignore
except ImportError:
    network = None  # type: ignore
    socket = None  # type: ignore

try:
    from lib.utils import sleep_ms, ticks_ms, ticks_diff
    from lib.config import save_config
except ImportError:
    # Fallback for testing outside MicroPython
    import time
    sleep_ms = lambda ms: time.sleep(ms / 1000.0)
    ticks_ms = lambda: int(time.time() * 1000)
    ticks_diff = lambda a, b: a - b
    save_config = lambda path, cfg: None


class SetupHTTPServer:
    """
    HTTP server for ongoing setup portal (runs after WiFi connection established).
    
    Handles HTTP requests on the specified port, allowing users to:
    - Reconfigure WiFi credentials
    - Center servo channels (if controller supports it)
    - View current configuration
    
    Args:
        controller: The MovementController instance (for accessing config and methods)
        port: HTTP port to listen on (default 80)
    """
    
    def __init__(self, controller, port):
        self._controller = controller
        self._port = port
        self.port = port
        self._sock = None
        self._start_socket()

    def _start_socket(self):
        """Start the HTTP server socket."""
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
        """Poll for incoming HTTP connections (non-blocking)."""
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
        """Handle an accepted HTTP client connection."""
        if client is None:
            return
        try:
            try:
                client.settimeout(2)
            except AttributeError:  # pragma: no cover
                pass
            method, path, headers, body = WiFiManager.read_http_request(client)
            if method is None:
                return
            status, response, _ = WiFiManager.handle_http_request(
                self._controller,
                method,
                path,
                headers,
                body,
                include_controls=True,
                trigger_reset=True,
                scanned_ssids=None,
            )
            WiFiManager.send_http_response(client, status, response)
        finally:
            try:
                client.close()
            except Exception:
                pass

    def close(self):
        """Close the HTTP server socket."""
        if self._sock is None:
            return
        try:
            self._sock.close()
        except Exception:
            pass
        self._sock = None


class WiFiManager:
    """
    WiFi connection manager with setup portal.
    
    Handles WiFi connection with automatic retry and fallback to a setup portal
    if credentials are missing or connection fails.
    
    The setup portal:
    - Creates an access point (AP mode)
    - Scans nearby WiFi networks
    - Presents a web interface for WiFi configuration
    - Saves credentials to config file
    
    Integrates with LEDStatus for visual feedback (breathing LED while disconnected).
    """
    
    @staticmethod
    def connect(config, led_status=None, on_portal_callback=None):
        """
        Connect to WiFi using credentials from config.
        
        If credentials are missing or connection fails, starts a setup portal
        where users can configure WiFi via a web interface.
        
        Args:
            config: Configuration dict with 'wifi' and 'setup_portal' sections
            led_status: Optional LEDStatus instance for visual feedback
            on_portal_callback: Optional callback function when portal is active
            
        Returns:
            network.WLAN station object if connected, None if network unavailable
            
        Raises:
            RuntimeError: If connection fails and portal times out without config
        """
        if network is None:
            return None
            
        station = network.WLAN(network.STA_IF)
        station.active(True)

        while True:
            wifi_cfg = config.get("wifi", {})
            ssid = (wifi_cfg.get("ssid") or "").strip()
            password = wifi_cfg.get("password")
            
            if not ssid:
                if not WiFiManager.start_config_portal(config, led_status, on_portal_callback):
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
                # Update breathing LED while waiting to connect
                if led_status:
                    try:
                        led_status.update_breathing()
                    except Exception:
                        pass
                retries += 1

            if station.isconnected():
                break

            try:
                station.disconnect()
            except Exception:
                pass

            if not WiFiManager.start_config_portal(config, led_status, on_portal_callback):
                raise RuntimeError("Wi-Fi connection timeout")
            station.active(True)

        return station

    @staticmethod
    def start_config_portal(config, led_status=None, on_portal_callback=None):
        """
        Start WiFi setup portal in AP mode.
        
        Creates an access point, scans nearby SSIDs, and presents a web interface
        for WiFi configuration. Runs until user submits credentials or timeout.
        
        Args:
            config: Configuration dict
            led_status: Optional LEDStatus for visual feedback
            on_portal_callback: Optional callback when portal starts
            
        Returns:
            True if WiFi credentials were updated, False if timeout or cancelled
        """
        if network is None:
            return False

        portal_cfg = config.get("setup_portal", {})
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
            sock.settimeout(0)
        except AttributeError:  # pragma: no cover
            try:
                sock.setblocking(False)  # type: ignore[attr-defined]
            except Exception:
                pass

        deadline = None
        if timeout_s > 0:
            deadline = ticks_ms() + timeout_s * 1000

        print('Starting setup portal; scanning nearby Wi-Fi networks...')
        # Scan SSIDs using station interface
        scanned_ssids = []
        try:
            try:
                station.active(True)
                scanned = station.scan() if hasattr(station, "scan") else []
            except Exception:
                scanned = []
            seen = set()
            for item in scanned:
                try:
                    ssid = item[0].decode("utf-8") if isinstance(item[0], (bytes, bytearray)) else str(item[0])
                except Exception:
                    ssid = str(item[0])
                ssid = ssid.strip()
                if ssid and ssid not in seen:
                    seen.add(ssid)
                    scanned_ssids.append(ssid)
            print('Scanned SSIDs:', scanned_ssids)
        finally:
            # Leave station inactive while portal is active
            try:
                station.active(False)
            except Exception:
                pass

        if on_portal_callback:
            try:
                on_portal_callback()
            except Exception:
                pass

        updated = False
        config_path = config.get("config_path", "movement_config.json")
        
        try:
            while True:
                if deadline is not None and ticks_diff(ticks_ms(), deadline) >= 0:
                    break
                try:
                    # Update breathing LED while waiting
                    if led_status:
                        try:
                            led_status.update_breathing()
                        except Exception:
                            pass
                    client, _ = sock.accept()
                except OSError:
                    sleep_ms(50)
                    continue

                status, response, result = ("200 OK", "", None)
                try:
                    method, path, headers, body = WiFiManager.read_http_request(client)
                    if method is not None:
                        status, response, result = WiFiManager.handle_http_request(
                            config,
                            method,
                            path,
                            headers,
                            body,
                            include_controls=False,
                            trigger_reset=False,
                            scanned_ssids=scanned_ssids,
                            config_path=config_path,
                        )
                finally:
                    try:
                        WiFiManager.send_http_response(client, status, response)
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

    @staticmethod
    def read_http_request(client):
        """
        Read and parse an HTTP request from a client socket.
        
        Args:
            client: Socket client connection
            
        Returns:
            Tuple of (method, path, headers_dict, body_string)
            Returns (None, "/", {}, "") if parsing fails
        """
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

    @staticmethod
    def send_http_response(client, status, body):
        """
        Send an HTTP response to a client socket.
        
        Args:
            client: Socket client connection
            status: HTTP status line (e.g., "200 OK")
            body: Response body (HTML string)
        """
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

    @staticmethod
    def handle_http_request(
        config_or_controller,
        method,
        path,
        headers,
        body,
        include_controls,
        trigger_reset,
        scanned_ssids=None,
        config_path=None,
    ):
        """
        Handle an HTTP request for the setup portal or ongoing server.
        
        Supports:
        - GET /: Show configuration form
        - POST /: Process WiFi credentials or servo control commands
        
        Args:
            config_or_controller: Either a config dict or MovementController instance
            method: HTTP method ("GET" or "POST")
            path: Request path
            headers: Request headers dict
            body: Request body string
            include_controls: Whether to show servo control buttons
            trigger_reset: Whether to schedule a reset after config save
            scanned_ssids: Optional list of scanned SSIDs for dropdown
            config_path: Optional config file path for saving
            
        Returns:
            Tuple of (status, response_html, result_code)
            result_code is "wifi_updated" if WiFi credentials were saved, None otherwise
        """
        # Support both dict and controller object
        if hasattr(config_or_controller, "config"):
            # It's a MovementController
            controller = config_or_controller
            config = controller.config
            config_path = config_path or controller._config_path
        else:
            # It's a config dict
            controller = None
            config = config_or_controller
            config_path = config_path or config.get("config_path", "movement_config.json")
        
        if path not in ("/", ""):
            return "404 Not Found", "<h1>Not Found</h1>", None

        if method == "POST":
            form = WiFiManager._parse_form(body or "")
            
            # Handle WiFi configuration
            ssid_val = None
            if "selected_ssid" in form:
                sel = form.get("selected_ssid", "").strip()
                if sel and sel != "__other__":
                    ssid_val = sel
                else:
                    # User chose Other; fall back to manual field
                    ssid_val = form.get("ssid_other", "").strip()
            elif "ssid" in form:
                # Backward compatibility
                ssid_val = form.get("ssid", "").strip()

            if ssid_val is not None:
                password_val = form.get("password", "")
                if not ssid_val:
                    html = WiFiManager._render_form_page(
                        config,
                        error="SSID is required",
                        include_controls=include_controls,
                        scanned_ssids=scanned_ssids,
                        controller=controller,
                    )
                    return "200 OK", html, None
                config.setdefault("wifi", {})
                config["wifi"]["ssid"] = ssid_val
                config["wifi"]["password"] = password_val
                save_config(config_path, config)
                print('Saved Wi-Fi credentials for SSID:', ssid_val)
                
                if trigger_reset and controller:
                    controller._pending_reset_at = ticks_ms() + 1500
                    
                return "200 OK", WiFiManager._render_success_page(ssid_val), "wifi_updated"

            # Handle servo controls (only if controller is available)
            if include_controls and controller:
                if "center_all" in form:
                    count = controller._center_all_servos() if hasattr(controller, "_center_all_servos") else 0
                    if count:
                        html = WiFiManager._render_form_page(
                            config,
                            message=f"Centered {count} channels.",
                            include_controls=True,
                            scanned_ssids=scanned_ssids,
                            controller=controller,
                        )
                    else:
                        html = WiFiManager._render_form_page(
                            config,
                            error="Unable to center servos — hardware not ready.",
                            include_controls=True,
                            scanned_ssids=scanned_ssids,
                            controller=controller,
                        )
                    return "200 OK", html, None
                    
                if "center" in form:
                    channel_raw = form.get("center", "")
                    try:
                        channel = int(channel_raw)
                    except ValueError:
                        channel = -1
                    success = controller._center_servo(channel) if hasattr(controller, "_center_servo") else False
                    if success:
                        html = WiFiManager._render_form_page(
                            config,
                            message=f"Centered channel {channel}.",
                            include_controls=True,
                            scanned_ssids=scanned_ssids,
                            controller=controller,
                        )
                    else:
                        html = WiFiManager._render_form_page(
                            config,
                            error="Invalid channel or hardware not ready.",
                            include_controls=True,
                            scanned_ssids=scanned_ssids,
                            controller=controller,
                        )
                    return "200 OK", html, None

        html = WiFiManager._render_form_page(
            config,
            include_controls=include_controls,
            scanned_ssids=scanned_ssids,
            controller=controller,
        )
        return "200 OK", html, None

    @staticmethod
    def _render_form_page(config, error=None, message=None, include_controls=False, scanned_ssids=None, controller=None):
        """Render the WiFi setup HTML form page."""
        wifi_cfg = config.get("wifi", {})
        ssid_value = WiFiManager._escape_html(wifi_cfg.get("ssid", ""))
        
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
            parts.append("<p style='color:#d33;'>%s</p>" % WiFiManager._escape_html(error))
        if message:
            parts.append("<p style='color:#4caf50;'>%s</p>" % WiFiManager._escape_html(message))

        # Render SSID selection
        ssid_input_html = []
        ssid_input_html.append("<form method='POST'>")
        if scanned_ssids:
            ssid_input_html.append("<label>Wi-Fi Network<select name='selected_ssid' id='selected_ssid' required>")
            ssid_input_html.append("<option value=''>-- Select a network --</option>")
            for s in scanned_ssids:
                s_esc = WiFiManager._escape_html(s)
                selected_attr = " selected" if s == wifi_cfg.get("ssid", "") else ""
                ssid_input_html.append(f"<option value='{s_esc}'{selected_attr}>{s_esc}</option>")
            ssid_input_html.append("<option value='__other__'>Other...</option>")
            ssid_input_html.append("</select></label>")
            
            # Manual entry field
            is_other = ssid_value and ssid_value not in scanned_ssids
            style = "display:block;" if is_other else "display:none;"
            ssid_input_html.append(
                f"<label id='ssid_other_label' style='{style}'>Manual SSID<input name='ssid_other' id='ssid_other' value='{ssid_value}' maxlength='64'></label>"
            )
        else:
            ssid_input_html.append(f"<label>Wi-Fi SSID<input name='ssid' value='{ssid_value}' maxlength='64' required></label>")

        ssid_input_html.append("<label>Password<input name='password' type='password' maxlength='64'></label>")
        ssid_input_html.append("<button type='submit'>Save &amp; Connect</button>")
        ssid_input_html.append("</form>")
        parts.extend(ssid_input_html)
        
        # JavaScript for SSID dropdown
        if scanned_ssids:
            parts.append(
                "<script>\n"
                "(function(){var sel=document.getElementById('selected_ssid');var other=document.getElementById('ssid_other_label');var otherInput=document.getElementById('ssid_other');if(!sel) return;sel.addEventListener('change',function(){if(sel.value=='__other__'){other.style.display='block';otherInput.required=true;}else{other.style.display='none';otherInput.required=false;}});})();\n"
                "</script>"
            )

        # Servo controls (if controller provided)
        if include_controls and controller:
            portal_cfg = config.get("setup_portal", {})
            port = int(portal_cfg.get("port", 80))
            default_center = config.get("default_center_pulse", 307)
            parts.append(
                f"<p class='meta'>HTTP portal active on port {port}."
                f" Default center pulse: {WiFiManager._escape_html(str(default_center))}.</p>"
            )
            controls_html = WiFiManager._build_center_controls(config, controller)
            if controls_html:
                parts.append(controls_html)

        parts.append("</body></html>")
        return "".join(parts)

    @staticmethod
    def _build_center_controls(config, controller):
        """Build servo centering controls HTML (if controller has PWM)."""
        if not controller or not hasattr(controller, "_pwm") or controller._pwm is None:
            return ""
            
        channels = int(config.get("servo_channel_count", 0) or 0)
        if channels <= 0:
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

    @staticmethod
    def _render_success_page(ssid):
        """Render success page after WiFi credentials saved."""
        ssid_html = WiFiManager._escape_html(ssid)
        return (
            "<!DOCTYPE html><html><head><meta charset='utf-8'>"
            "<meta name='viewport' content='width=device-width,initial-scale=1'>"
            "<title>Credentials Saved</title>"
            "<style>body{{font-family:Arial,Helvetica,sans-serif;padding:24px;"
            "background:#101820;color:#f2f2f2;}}a{{color:#ff6f3c;}}</style></head><body>"
            "<h1>Credentials saved</h1>"
            f"<p>The ESP32 will now reboot and try to join <strong>{ssid_html}</strong>.</p>"
            "<p>You can disconnect from the setup Wi-Fi network.</p>"
            "</body></html>"
        )

    @staticmethod
    def _parse_form(body):
        """Parse URL-encoded form data."""
        data = {}
        if not body:
            return data
        for pair in body.split("&"):
            if "=" not in pair:
                continue
            key, value = pair.split("=", 1)
            data[WiFiManager._url_decode(key)] = WiFiManager._url_decode(value)
        return data

    @staticmethod
    def _url_decode(value):
        """Decode URL-encoded string."""
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
        """Escape HTML special characters."""
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


# Self-tests (run when module is executed directly)
if __name__ == "__main__":
    print("Running wifi_manager self-tests...")
    
    # Test 1: URL decode
    assert WiFiManager._url_decode("hello+world") == "hello world"
    assert WiFiManager._url_decode("test%20space") == "test space"
    assert WiFiManager._url_decode("My%20Wi-Fi") == "My Wi-Fi"
    print("✓ URL decode")
    
    # Test 2: HTML escape
    assert WiFiManager._escape_html("<script>") == "&lt;script&gt;"
    assert WiFiManager._escape_html("A & B") == "A &amp; B"
    assert WiFiManager._escape_html('"test"') == "&quot;test&quot;"
    print("✓ HTML escape")
    
    # Test 3: Form parsing
    form = WiFiManager._parse_form("ssid=MyWiFi&password=secret123")
    assert form["ssid"] == "MyWiFi"
    assert form["password"] == "secret123"
    print("✓ Form parsing")
    
    # Test 4: Empty form
    form = WiFiManager._parse_form("")
    assert form == {}
    print("✓ Empty form")
    
    # Test 5: Form with URL encoding
    form = WiFiManager._parse_form("ssid=My+WiFi&password=p%40ss")
    assert form["ssid"] == "My WiFi"
    assert form["password"] == "p@ss"
    print("✓ Form with URL encoding")
    
    # Test 6: Render success page
    html = WiFiManager._render_success_page("TestNetwork")
    assert "TestNetwork" in html
    assert "saved" in html.lower()
    print("✓ Success page rendering")
    
    # Test 7: Render form page
    config = {"wifi": {"ssid": "existing"}}
    html = WiFiManager._render_form_page(config)
    assert "TARS" in html
    assert "Wi-Fi" in html
    print("✓ Form page rendering")
    
    print("\n✓ All wifi_manager tests passed!")
