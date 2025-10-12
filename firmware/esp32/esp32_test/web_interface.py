"""
Web Interface for TARS Servo Controller
Provides HTTP server with interactive web UI
"""

import socket
import network
import time
import json
import gc
from servo_controller import ServoController
import servo_config as config
import wifi_config


class WebInterface:
    """Web server for servo control"""
    
    def __init__(self):
        """Initialize web interface"""
        self.controller = None
        self.wlan = None
        self.ap = None
        self.sock = None
        
    def connect_wifi(self):
        """Connect to WiFi network"""
        # Skip WiFi if SSID is empty or not configured
        if not wifi_config.WIFI_SSID or wifi_config.WIFI_SSID.strip() == "":
            print("\n=== WiFi Not Configured ===")
            print("WiFi SSID is empty, skipping WiFi connection")
            print("Will use Access Point mode instead")
            return False
        
        print("\n=== WiFi Connection ===")
        
        self.wlan = network.WLAN(network.STA_IF)
        self.wlan.active(True)
        
        if self.wlan.isconnected():
            print("Already connected to WiFi")
            return True
        
        print(f"Connecting to {wifi_config.WIFI_SSID}...")
        self.wlan.connect(wifi_config.WIFI_SSID, wifi_config.WIFI_PASSWORD)
        
        # Wait for connection
        timeout = 15
        while timeout > 0:
            if self.wlan.isconnected():
                status = self.wlan.ifconfig()
                print(f"✓ Connected!")
                print(f"  IP Address: {status[0]}")
                print(f"  Netmask: {status[1]}")
                print(f"  Gateway: {status[2]}")
                return True
            time.sleep(1)
            timeout -= 1
            print(".", end="")
        
        print("\n✗ WiFi connection failed")
        return False
    
    def start_access_point(self):
        """Start Access Point mode as fallback"""
        if not wifi_config.AP_ENABLED:
            return False
        
        print("\n=== Starting Access Point ===")
        
        self.ap = network.WLAN(network.AP_IF)
        self.ap.active(True)
        self.ap.config(essid=wifi_config.AP_SSID, password=wifi_config.AP_PASSWORD)
        
        timeout = 10
        while timeout > 0:
            if self.ap.active():
                status = self.ap.ifconfig()
                print(f"✓ Access Point Started!")
                print(f"  SSID: {wifi_config.AP_SSID}")
                print(f"  Password: {wifi_config.AP_PASSWORD}")
                print(f"  IP Address: {status[0]}")
                return True
            time.sleep(1)
            timeout -= 1
        
        print("✗ Failed to start Access Point")
        return False
    
    def get_html_page(self):
        """Generate HTML page for servo control"""
        html = """<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>TARS Servo Controller v2.0</title>
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; }
        body {
            font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            min-height: 100vh;
            padding: 20px;
        }
        .container {
            max-width: 1200px;
            margin: 0 auto;
            background: white;
            border-radius: 15px;
            box-shadow: 0 20px 60px rgba(0,0,0,0.3);
            padding: 30px;
        }
        h1 {
            text-align: center;
            color: #333;
            margin-bottom: 10px;
            font-size: 2.5em;
        }
        .subtitle {
            text-align: center;
            color: #666;
            margin-bottom: 30px;
            font-size: 1.1em;
        }
        .status-bar {
            background: #f8f9fa;
            padding: 15px;
            border-radius: 10px;
            margin-bottom: 30px;
            display: flex;
            justify-content: space-around;
            flex-wrap: wrap;
            gap: 15px;
        }
        .status-item {
            display: flex;
            flex-direction: column;
            align-items: center;
        }
        .status-label {
            font-size: 0.9em;
            color: #666;
            margin-bottom: 5px;
        }
        .status-value {
            font-size: 1.3em;
            font-weight: bold;
            color: #667eea;
        }
        .controls {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(300px, 1fr));
            gap: 20px;
            margin-bottom: 30px;
        }
        .servo-card {
            background: #f8f9fa;
            padding: 20px;
            border-radius: 10px;
            box-shadow: 0 2px 10px rgba(0,0,0,0.1);
        }
        .servo-header {
            display: flex;
            justify-content: space-between;
            align-items: center;
            margin-bottom: 15px;
        }
        .servo-title {
            font-size: 1.2em;
            font-weight: bold;
            color: #333;
        }
        .servo-channel {
            background: #667eea;
            color: white;
            padding: 5px 10px;
            border-radius: 5px;
            font-size: 0.9em;
        }
        .servo-controls {
            display: flex;
            flex-direction: column;
            gap: 10px;
        }
        .slider-container {
            display: flex;
            align-items: center;
            gap: 10px;
        }
        .slider {
            flex: 1;
            height: 8px;
            border-radius: 5px;
            background: #ddd;
            outline: none;
            -webkit-appearance: none;
        }
        .slider::-webkit-slider-thumb {
            -webkit-appearance: none;
            appearance: none;
            width: 20px;
            height: 20px;
            border-radius: 50%;
            background: #667eea;
            cursor: pointer;
        }
        .slider::-moz-range-thumb {
            width: 20px;
            height: 20px;
            border-radius: 50%;
            background: #667eea;
            cursor: pointer;
            border: none;
        }
        .value-display {
            min-width: 60px;
            text-align: center;
            font-weight: bold;
            color: #333;
        }
        .button-group {
            display: flex;
            gap: 10px;
            margin-top: 10px;
        }
        .btn {
            flex: 1;
            padding: 10px;
            border: none;
            border-radius: 5px;
            font-size: 0.9em;
            cursor: pointer;
            transition: all 0.3s;
        }
        .btn-primary {
            background: #667eea;
            color: white;
        }
        .btn-primary:hover {
            background: #5568d3;
        }
        .btn-success {
            background: #10b981;
            color: white;
        }
        .btn-success:hover {
            background: #059669;
        }
        .btn-danger {
            background: #ef4444;
            color: white;
        }
        .btn-danger:hover {
            background: #dc2626;
        }
        .btn-warning {
            background: #f59e0b;
            color: white;
        }
        .btn-warning:hover {
            background: #d97706;
        }
        .global-controls {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
            gap: 15px;
            margin-top: 30px;
        }
        .global-btn {
            padding: 15px;
            border: none;
            border-radius: 10px;
            font-size: 1.1em;
            cursor: pointer;
            transition: all 0.3s;
            font-weight: bold;
        }
        .message {
            position: fixed;
            top: 20px;
            right: 20px;
            padding: 15px 25px;
            border-radius: 10px;
            background: #10b981;
            color: white;
            box-shadow: 0 5px 15px rgba(0,0,0,0.3);
            display: none;
            z-index: 1000;
        }
        .message.show {
            display: block;
            animation: slideIn 0.3s ease;
        }
        @keyframes slideIn {
            from { transform: translateX(100%); opacity: 0; }
            to { transform: translateX(0); opacity: 1; }
        }
        .footer {
            text-align: center;
            color: #666;
            margin-top: 30px;
            padding-top: 20px;
            border-top: 2px solid #eee;
        }
    </style>
</head>
<body>
    <div id="message" class="message"></div>
    
    <div class="container">
        <h1>🤖 TARS Servo Controller</h1>
        <div class="subtitle">ESP32 Web Interface</div>
        
        <div class="status-bar">
            <div class="status-item">
                <div class="status-label">Status</div>
                <div class="status-value" id="status">Ready</div>
            </div>
            <div class="status-item">
                <div class="status-label">Active Servos</div>
                <div class="status-value" id="active-servos">0/9</div>
            </div>
            <div class="status-item">
                <div class="status-label">Last Update</div>
                <div class="status-value" id="last-update">--:--:--</div>
            </div>
        </div>
        
        <div class="controls" id="servo-controls"></div>
        
        <div class="global-controls">
            <button class="global-btn btn-success" onclick="setNeutral()">🏠 Neutral Position</button>
            <button class="global-btn btn-primary" onclick="testAll()">🔄 Test All Servos</button>
            <button class="global-btn btn-warning" onclick="refreshPositions()">📊 Refresh Positions</button>
            <button class="global-btn btn-danger" onclick="disableAll()">⛔ Disable All</button>
        </div>
        
        <div class="header">
            <h2 style="margin: 0;">🤖 Movement Poses</h2>
        </div>
        
        <div class="global-controls">
            <h3 style="margin: 10px 0; color: #fff;">Movement</h3>
            <button class="global-btn btn-primary" onclick="executePose('reset')">🔄 Reset</button>
            <button class="global-btn btn-primary" onclick="executePose('forward')">⬆️ Forward</button>
            <button class="global-btn btn-primary" onclick="executePose('backward')">⬇️ Backward</button>
            <button class="global-btn btn-primary" onclick="executePose('turn_right')">➡️ Turn Right</button>
            <button class="global-btn btn-primary" onclick="executePose('turn_left')">⬅️ Turn Left</button>
        </div>
        
        <div class="global-controls">
            <h3 style="margin: 10px 0; color: #fff;">Gestures</h3>
            <button class="global-btn btn-success" onclick="executePose('greet')">👋 Greet / Wave</button>
            <button class="global-btn btn-success" onclick="executePose('now')">☝️ Now!</button>
            <button class="global-btn btn-success" onclick="executePose('bow')">🙇 Bow</button>
            <button class="global-btn btn-success" onclick="executePose('pose')">💪 Strike Pose</button>
        </div>
        
        <div class="global-controls">
            <h3 style="margin: 10px 0; color: #fff;">Actions</h3>
            <button class="global-btn btn-warning" onclick="executePose('laugh')">😂 Laugh</button>
            <button class="global-btn btn-warning" onclick="executePose('swing_legs')">🦵 Swing Legs</button>
            <button class="global-btn btn-warning" onclick="executePose('balance')">⚖️ Balance</button>
            <button class="global-btn btn-warning" onclick="executePose('pezz')">🍬 PEZZ Dispenser</button>
        </div>
        
        <div class="global-controls">
            <h3 style="margin: 10px 0; color: #fff;">Special</h3>
            <button class="global-btn btn-danger" onclick="executePose('mic_drop')">🎤 Mic Drop</button>
            <button class="global-btn btn-danger" onclick="executePose('defensive')">👹 Defensive</button>
        </div>
        
        <div class="footer">
            <p>TARS Servo Controller v2.0 (Poses Edition) | MicroPython ESP32</p>
        </div>
    </div>
    
    <script>
        const servoNames = [
            'Main Legs (Height)',
            'Left Leg Rotation',
            'Right Leg Rotation',
            'Right Arm Main',
            'Right Arm Forearm',
            'Right Arm Hand',
            'Left Arm Main',
            'Left Arm Forearm',
            'Left Arm Hand'
        ];
        
        const servoRanges = SERVO_RANGES_PLACEHOLDER;
        
        function initializeControls() {
            const container = document.getElementById('servo-controls');
            for (let i = 0; i < 9; i++) {
                const range = servoRanges[i];
                const card = document.createElement('div');
                card.className = 'servo-card';
                card.innerHTML = `
                    <div class="servo-header">
                        <div class="servo-title">${servoNames[i]}</div>
                        <div class="servo-channel">CH ${i}</div>
                    </div>
                    <div class="servo-controls">
                        <div class="slider-container">
                            <input type="range" class="slider" id="slider-${i}" 
                                   min="${range.min}" max="${range.max}" value="${range.default}"
                                   oninput="updateValue(${i}, this.value)">
                            <div class="value-display" id="value-${i}">${range.default}</div>
                        </div>
                        <div class="button-group">
                            <button class="btn btn-primary" onclick="setServo(${i})">Set</button>
                            <button class="btn btn-success" onclick="testServo(${i})">Test</button>
                        </div>
                    </div>
                `;
                container.appendChild(card);
            }
        }
        
        function updateValue(channel, value) {
            document.getElementById(`value-${channel}`).textContent = value;
        }
        
        function showMessage(text, type = 'success') {
            const msg = document.getElementById('message');
            msg.textContent = text;
            msg.style.background = type === 'error' ? '#ef4444' : '#10b981';
            msg.classList.add('show');
            setTimeout(() => msg.classList.remove('show'), 3000);
        }
        
        function updateStatus() {
            document.getElementById('last-update').textContent = 
                new Date().toLocaleTimeString();
        }
        
        async function apiCall(endpoint, data = null) {
            try {
                const response = await fetch(endpoint, {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: data ? JSON.stringify(data) : null
                });
                const result = await response.json();
                updateStatus();
                return result;
            } catch (error) {
                showMessage('Connection error: ' + error.message, 'error');
                return { success: false, error: error.message };
            }
        }
        
        async function setServo(channel) {
            const value = parseInt(document.getElementById(`slider-${channel}`).value);
            document.getElementById('status').textContent = 'Moving...';
            const result = await apiCall('/servo', { channel, pulse: value });
            if (result.success) {
                showMessage(`Servo ${channel} moved to ${value}`);
                document.getElementById('status').textContent = 'Ready';
            } else {
                showMessage('Error: ' + (result.error || 'Unknown'), 'error');
                document.getElementById('status').textContent = 'Error';
            }
        }
        
        async function testServo(channel) {
            document.getElementById('status').textContent = 'Testing...';
            showMessage(`Testing servo ${channel}...`);
            const result = await apiCall('/test', { channel });
            if (result.success) {
                showMessage(`Servo ${channel} test complete`);
                document.getElementById('status').textContent = 'Ready';
            } else {
                showMessage('Error: ' + (result.error || 'Unknown'), 'error');
                document.getElementById('status').textContent = 'Error';
            }
        }
        
        async function setNeutral() {
            document.getElementById('status').textContent = 'Moving...';
            showMessage('Moving to neutral position...');
            const result = await apiCall('/preset', { name: 'neutral' });
            if (result.success) {
                showMessage('Neutral position set');
                document.getElementById('status').textContent = 'Ready';
                // Update sliders to neutral positions
                for (let i = 0; i < 9; i++) {
                    const range = servoRanges[i];
                    document.getElementById(`slider-${i}`).value = range.default;
                    document.getElementById(`value-${i}`).textContent = range.default;
                }
            }
        }
        
        async function testAll() {
            if (!confirm('This will test all 9 servos sequentially. Continue?')) return;
            document.getElementById('status').textContent = 'Testing All...';
            showMessage('Testing all servos...');
            const result = await apiCall('/testall', {});
            if (result.success) {
                showMessage('All servos tested successfully');
                document.getElementById('status').textContent = 'Ready';
            }
        }
        
        async function refreshPositions() {
            const result = await apiCall('/positions', {});
            if (result.success && result.positions) {
                for (let i = 0; i < 9; i++) {
                    const pos = result.positions[i];
                    document.getElementById(`slider-${i}`).value = pos;
                    document.getElementById(`value-${i}`).textContent = pos;
                }
                showMessage('Positions refreshed');
            }
        }
        
        async function disableAll() {
            if (!confirm('Disable all servos?')) return;
            document.getElementById('status').textContent = 'Disabling...';
            const result = await apiCall('/disable', {});
            if (result.success) {
                showMessage('All servos disabled');
                document.getElementById('status').textContent = 'Disabled';
            }
        }
        
        async function executePose(poseName) {
            alert('Button clicked: ' + poseName);
            console.log('executePose called with:', poseName);
            document.getElementById('status').textContent = `Executing ${poseName}...`;
            showMessage(`Executing pose: ${poseName}`);
            try {
                const result = await apiCall(`/pose/${poseName}`, {});
                console.log('Pose result:', result);
                if (result.success) {
                    showMessage(`Pose "${poseName}" complete!`);
                    document.getElementById('status').textContent = 'Ready';
                } else {
                    showMessage(`Error: ${result.error || 'Unknown error'}`, true);
                    document.getElementById('status').textContent = 'Error';
                }
            } catch (error) {
                console.error('Error in executePose:', error);
                alert('Error: ' + error.message);
            }
        }
        
        // Initialize on load
        window.onload = function() {
            console.log('Page loaded - TARS v2.0 with Poses');
            console.log('executePose function exists:', typeof executePose === 'function');
            initializeControls();
        };
    </script>
</body>
</html>"""
        return html
    
    def handle_request(self, request):
        """Handle HTTP request and return response"""
        try:
            # Parse request
            lines = request.decode('utf-8').split('\r\n')
            if not lines:
                return None
            
            request_line = lines[0]
            parts = request_line.split(' ')
            if len(parts) < 2:
                return None
            
            method = parts[0]
            path = parts[1]
            print(f"DEBUG: {method} {path}")
            
            # Extract body for POST requests
            body = None
            if method == 'POST':
                try:
                    body_start = request.find(b'\r\n\r\n')
                    if body_start != -1:
                        body_data = request[body_start + 4:].decode('utf-8')
                        if body_data:
                            body = json.loads(body_data)
                except:
                    pass
            
            # Route requests
            if path == '/' or path.startswith('/?'):
                return self.serve_html()
            elif path == '/servo' and method == 'POST':
                return self.handle_servo(body)
            elif path == '/test' and method == 'POST':
                return self.handle_test(body)
            elif path == '/testall' and method == 'POST':
                return self.handle_test_all()
            elif path == '/preset' and method == 'POST':
                return self.handle_preset(body)
            elif path == '/positions' and method == 'POST':
                return self.handle_positions()
            elif path == '/disable' and method == 'POST':
                return self.handle_disable()
            elif path == '/pose/reset' and method == 'POST':
                return self.handle_pose('reset')
            elif path == '/pose/forward' and method == 'POST':
                return self.handle_pose('forward')
            elif path == '/pose/backward' and method == 'POST':
                return self.handle_pose('backward')
            elif path == '/pose/turn_right' and method == 'POST':
                return self.handle_pose('turn_right')
            elif path == '/pose/turn_left' and method == 'POST':
                return self.handle_pose('turn_left')
            elif path == '/pose/greet' and method == 'POST':
                return self.handle_pose('greet')
            elif path == '/pose/laugh' and method == 'POST':
                return self.handle_pose('laugh')
            elif path == '/pose/swing_legs' and method == 'POST':
                return self.handle_pose('swing_legs')
            elif path == '/pose/pezz' and method == 'POST':
                return self.handle_pose('pezz')
            elif path == '/pose/now' and method == 'POST':
                return self.handle_pose('now')
            elif path == '/pose/balance' and method == 'POST':
                return self.handle_pose('balance')
            elif path == '/pose/mic_drop' and method == 'POST':
                return self.handle_pose('mic_drop')
            elif path == '/pose/defensive' and method == 'POST':
                return self.handle_pose('defensive')
            elif path == '/pose/pose' and method == 'POST':
                return self.handle_pose('pose')
            elif path == '/pose/bow' and method == 'POST':
                return self.handle_pose('bow')
            
            return self.json_response({'error': 'Not found'}, 404)
            
        except Exception as e:
            print(f"Request error: {e}")
            return self.json_response({'error': str(e)}, 500)
    
    def serve_html(self):
        """Serve main HTML page - returns tuple for chunked transmission"""
        html = self.get_html_page()
        
        # Inject servo ranges
        ranges_json = json.dumps([config.get_servo_range(i) for i in range(9)])
        html = html.replace('SERVO_RANGES_PLACEHOLDER', ranges_json)
        
        # Encode body FIRST to get accurate byte count
        body_bytes = html.encode('utf-8')
        
        # Build headers with accurate Content-Length
        headers = 'HTTP/1.1 200 OK\r\n'
        headers += 'Content-Type: text/html; charset=utf-8\r\n'
        headers += 'Cache-Control: no-cache, no-store, must-revalidate\r\n'
        headers += 'Pragma: no-cache\r\n'
        headers += 'Expires: 0\r\n'
        headers += f'Content-Length: {len(body_bytes)}\r\n'
        headers += 'Connection: close\r\n\r\n'
        
        print(f"HTML body size: {len(body_bytes)} bytes")
        
        # Return tuple: (headers_bytes, body_bytes)
        return (headers.encode('utf-8'), body_bytes)
    
    def json_response(self, data, status=200):
        """Create JSON response"""
        json_str = json.dumps(data)
        response = f'HTTP/1.1 {status} OK\r\n'
        response += 'Content-Type: application/json\r\n'
        response += f'Content-Length: {len(json_str)}\r\n'
        response += 'Connection: close\r\n\r\n'
        response += json_str
        return response.encode('utf-8')
    
    def handle_servo(self, data):
        """Handle servo position command"""
        try:
            channel = data.get('channel')
            pulse = data.get('pulse')
            
            if channel is None or pulse is None:
                return self.json_response({'success': False, 'error': 'Missing parameters'}, 400)
            
            success = self.controller.set_servo_pulse(channel, pulse)
            return self.json_response({'success': success})
        except Exception as e:
            return self.json_response({'success': False, 'error': str(e)}, 500)
    
    def handle_test(self, data):
        """Handle servo test command"""
        try:
            channel = data.get('channel')
            if channel is None:
                return self.json_response({'success': False, 'error': 'Missing channel'}, 400)
            
            self.controller.test_servo(channel, delay_ms=1000)
            return self.json_response({'success': True})
        except Exception as e:
            return self.json_response({'success': False, 'error': str(e)}, 500)
    
    def handle_test_all(self):
        """Handle test all servos command"""
        try:
            self.controller.test_all_servos(delay_ms=1000)
            return self.json_response({'success': True})
        except Exception as e:
            return self.json_response({'success': False, 'error': str(e)}, 500)
    
    def handle_preset(self, data):
        """Handle preset position command"""
        try:
            name = data.get('name', 'neutral')
            success = self.controller.set_preset(name)
            return self.json_response({'success': success})
        except Exception as e:
            return self.json_response({'success': False, 'error': str(e)}, 500)
    
    def handle_positions(self):
        """Handle get positions command"""
        try:
            positions = [self.controller.get_position(i) for i in range(9)]
            return self.json_response({'success': True, 'positions': positions})
        except Exception as e:
            return self.json_response({'success': False, 'error': str(e)}, 500)
    
    def handle_disable(self):
        """Handle disable all servos command"""
        try:
            self.controller.disable_all_servos()
            return self.json_response({'success': True})
        except Exception as e:
            return self.json_response({'success': False, 'error': str(e)}, 500)
    
    def handle_pose(self, pose_name):
        """Handle pose/movement command"""
        try:
            print(f"DEBUG: Received pose request: {pose_name}")
            pose_map = {
                'reset': self.controller.reset_positions,
                'forward': self.controller.step_forward,
                'backward': self.controller.step_backward,
                'turn_right': self.controller.turn_right,
                'turn_left': self.controller.turn_left,
                'greet': self.controller.greet,
                'laugh': self.controller.laugh,
                'swing_legs': self.controller.swing_legs,
                'pezz': self.controller.pezz_dispenser,
                'now': self.controller.now,
                'balance': self.controller.balance,
                'mic_drop': self.controller.mic_drop,
                'defensive': self.controller.defensive_posture,
                'pose': self.controller.pose,
                'bow': self.controller.bow,
            }
            
            if pose_name not in pose_map:
                print(f"ERROR: Unknown pose: {pose_name}")
                return self.json_response({'success': False, 'error': 'Unknown pose'}, 400)
            
            # Execute pose
            print(f"Executing pose: {pose_name}")
            pose_map[pose_name]()
            print(f"Pose {pose_name} complete")
            return self.json_response({'success': True, 'pose': pose_name})
        except Exception as e:
            print(f"ERROR in pose {pose_name}: {e}")
            return self.json_response({'success': False, 'error': str(e)}, 500)
    
    def start_server(self):
        """Start the web server"""
        print("\n=== Starting Web Server ===")
        
        # Initialize servo controller
        try:
            self.controller = ServoController()
            print("Servo controller initialized")
        except Exception as e:
            print(f"ERROR: Failed to initialize servo controller: {e}")
            return False
        
        # Set to neutral position
        self.controller.set_preset('neutral')
        
        # Create socket
        addr = socket.getaddrinfo('0.0.0.0', wifi_config.WEB_PORT)[0][-1]
        self.sock = socket.socket()
        self.sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.sock.bind(addr)
        self.sock.listen(5)
        
        # Get IP address
        if self.wlan and self.wlan.isconnected():
            ip = self.wlan.ifconfig()[0]
        elif self.ap and self.ap.active():
            ip = self.ap.ifconfig()[0]
        else:
            ip = 'unknown'
        
        print(f"\n{'='*50}")
        print(f"✓ Web Server Running!")
        print(f"{'='*50}")
        print(f"  URL: http://{ip}:{wifi_config.WEB_PORT}")
        print(f"  Open this URL in your web browser")
        print(f"{'='*50}\n")
        
        # Main server loop
        while True:
            try:
                conn, addr = self.sock.accept()
                conn.settimeout(5.0)
                
                # Receive request
                request = b''
                try:
                    while True:
                        chunk = conn.recv(1024)
                        if not chunk:
                            break
                        request += chunk
                        if b'\r\n\r\n' in request:
                            # Check if there's a content-length
                            if b'Content-Length:' in request:
                                headers = request.split(b'\r\n\r\n')[0]
                                for line in headers.split(b'\r\n'):
                                    if line.startswith(b'Content-Length:'):
                                        content_length = int(line.split(b':')[1].strip())
                                        body_received = len(request.split(b'\r\n\r\n')[1])
                                        if body_received >= content_length:
                                            break
                            else:
                                break
                except:
                    pass
                
                # Handle request
                if request:
                    response = self.handle_request(request)
                    if response:
                        # Check if response is tuple (headers, body) for HTML
                        if isinstance(response, tuple):
                            headers, body = response
                            print(f"Sending {len(headers)} header bytes, {len(body)} body bytes")
                            
                            # Send headers first
                            conn.send(headers)
                            gc.collect()
                            
                            # Send body in small chunks with aggressive GC
                            chunk_size = 1024
                            chunks_sent = 0
                            for i in range(0, len(body), chunk_size):
                                chunk = body[i:i+chunk_size]
                                conn.send(chunk)
                                chunks_sent += 1
                                if chunks_sent % 4 == 0:  # GC every 4KB
                                    gc.collect()
                                time.sleep_ms(10)
                            
                            print(f"Sent {chunks_sent} chunks total")
                        else:
                            # Regular response (JSON)
                            conn.send(response)
                
                conn.close()
                gc.collect()  # Clean up memory
                
            except KeyboardInterrupt:
                print("\n\nShutting down...")
                self.controller.disable_all_servos()
                break
            except Exception as e:
                print(f"Connection error: {e}")
                try:
                    conn.close()
                except:
                    pass
        
        # Cleanup
        if self.sock:
            self.sock.close()
        return True
    
    def run(self):
        """Main entry point"""
        print("\n" + "="*50)
        print("TARS Servo Controller - Web Interface")
        print("="*50)
        
        # Try WiFi connection first (skip if SSID is empty)
        if self.connect_wifi():
            print("\n✓ WiFi connected, starting web server...")
        elif self.start_access_point():
            print("\n✓ Access Point started, starting web server...")
        else:
            print("\n✗ Network connection failed!")
            print("Please check wifi_config.py settings")
            print("Or enable Access Point mode (AP_ENABLED = True)")
            return False
        
        # Start web server
        return self.start_server()


def main():
    """Run the web interface"""
    interface = WebInterface()
    interface.run()


if __name__ == '__main__':
    main()
