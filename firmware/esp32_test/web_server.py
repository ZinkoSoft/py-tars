"""
Web Server for ESP32 Servo Controller
Async HTTP server with embedded HTML interface
"""

import uasyncio as asyncio
import json
import gc
import time
from wifi_manager import get_wifi_status


# Embedded HTML interface (compact to save memory)
HTML_INTERFACE = """<!DOCTYPE html>
<html>
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>TARS Servo Controller</title>
<style>
body{font-family:Arial,sans-serif;margin:0;padding:20px;background:#1a1a1a;color:#fff}
.container{max-width:1200px;margin:0 auto}
h1{text-align:center;color:#4CAF50}
.emergency{position:fixed;top:20px;right:20px;z-index:1000;background:#f44336;color:#fff;border:none;border-radius:50%;width:80px;height:80px;font-size:14px;font-weight:bold;cursor:pointer;box-shadow:0 4px 8px rgba(0,0,0,0.3)}
.emergency:hover{background:#d32f2f}
.resume{position:fixed;top:110px;right:20px;z-index:1000;background:#ff9800;color:#fff;border:none;border-radius:8px;padding:12px 20px;font-size:14px;font-weight:bold;cursor:pointer}
.section{background:#2d2d2d;padding:20px;margin:20px 0;border-radius:8px}
.servo-control{margin:15px 0;padding:15px;background:#383838;border-radius:5px}
.servo-label{font-weight:bold;margin-bottom:10px;color:#4CAF50}
.input-group{display:flex;gap:10px;margin:10px 0;flex-wrap:wrap;align-items:center}
.input-group input,.input-group button{padding:8px;border-radius:4px;border:1px solid #555;background:#2d2d2d;color:#fff}
.input-group input[type="number"]{width:80px}
.input-group button{background:#4CAF50;border:none;cursor:pointer;min-width:100px}
.input-group button:hover{background:#45a049}
.servo-slider{flex:1;min-width:200px;margin:0 10px}
.slider-value{min-width:50px;text-align:right;color:#4CAF50;font-weight:bold}
.speed-control{margin:20px 0}
.speed-slider{width:100%;margin:10px 0}
.presets{display:grid;grid-template-columns:repeat(auto-fill,minmax(150px,1fr));gap:10px;margin:20px 0}
.preset-btn{padding:15px;background:#2196F3;color:#fff;border:none;border-radius:5px;cursor:pointer;font-size:14px}
.preset-btn:hover{background:#1976D2}
.status-panel{background:#383838;padding:15px;border-radius:5px;margin:20px 0}
.status-item{margin:5px 0}
#message{padding:10px;margin:10px 0;border-radius:5px;background:#4CAF50;display:none}
#error{padding:10px;margin:10px 0;border-radius:5px;background:#f44336;display:none}
</style>
</head>
<body>
<div class="container">
<h1>🤖 TARS Servo Controller</h1>
<button class="emergency" onclick="emergencyStop()">STOP</button>
<button class="resume" onclick="resume()">Resume</button>
<div id="message"></div>
<div id="error"></div>
<div class="section">
<h2>Global Speed Control</h2>
<div class="speed-control">
<label>Speed: <span id="speedDisplay">1.0</span>x</label>
<input type="range" class="speed-slider" id="globalSpeed" min="0.1" max="10.0" step="0.1" value="1.0" oninput="updateGlobalSpeed()">
<small>0.1 = slowest, 1.0 = normal, 1.5 = 50% faster, 10.0 = maximum</small>
<div style="margin-top:10px">
<button onclick="setSpeed(1.0)" style="padding:5px 10px;margin:2px">1.0x</button>
<button onclick="setSpeed(1.5)" style="padding:5px 10px;margin:2px;background:#ff9800">1.5x</button>
<button onclick="setSpeed(2.0)" style="padding:5px 10px;margin:2px">2.0x</button>
<button onclick="setSpeed(3.0)" style="padding:5px 10px;margin:2px">3.0x</button>
<button onclick="setSpeed(5.0)" style="padding:5px 10px;margin:2px;background:#f44336">5.0x</button>
<button onclick="setSpeed(10.0)" style="padding:5px 10px;margin:2px;background:#d32f2f">10.0x</button>
</div>
</div>
</div>
<div class="section">
<h2>Individual Servo Control</h2>
<div id="servos"></div>
</div>
<div class="section">
<h2>Preset Movements</h2>
<div id="status-indicator" style="text-align:center;margin:10px 0;color:#ff9800"></div>
<div style="margin:15px 0;text-align:center">
<label>Repeat: </label>
<input type="number" id="presetRepeat" min="1" max="50" value="1" style="width:60px;padding:5px;border-radius:4px;border:1px solid #555;background:#2d2d2d;color:#fff">
<span style="margin:0 10px;color:#888;font-size:12px">1-50 times</span>
<label style="margin-left:20px">Delay: </label>
<input type="number" id="presetDelay" min="0.1" max="2.0" step="0.1" value="1.0" style="width:60px;padding:5px;border-radius:4px;border:1px solid #555;background:#2d2d2d;color:#fff">
<span style="margin-left:5px;color:#888;font-size:12px">0.1-2.0x</span>
</div>
<div class="presets" id="presets"></div>
</div>
<div class="section">
<h2>System Status</h2>
<button onclick="getStatus()" style="padding:10px 20px;background:#2196F3;color:#fff;border:none;border-radius:5px;cursor:pointer;margin-bottom:15px">Refresh Status</button>
<div class="status-panel" id="status"></div>
</div>
</div>
<script>
const servos=[
{ch:0,label:"Main Legs Lift",min:220,max:360},
{ch:1,label:"Left Leg Rotation",min:192,max:408},
{ch:2,label:"Right Leg Rotation",min:192,max:408},
{ch:3,label:"Right Shoulder",min:135,max:440},
{ch:4,label:"Right Elbow",min:200,max:380},
{ch:5,label:"Right Hand",min:200,max:280},
{ch:6,label:"Left Shoulder",min:135,max:440},
{ch:7,label:"Left Elbow",min:200,max:380},
{ch:8,label:"Left Hand",min:280,max:380}
];
const presets=[
{name:"reset_positions",label:"Reset All"},
{name:"step_forward",label:"Step Forward"},
{name:"step_backward",label:"Step Back"},
{name:"turn_right",label:"Turn Right"},
{name:"turn_left",label:"Turn Left"},
{name:"right_hi",label:"Wave/Greet"},
{name:"laugh",label:"Laugh"},
{name:"swing_legs",label:"Swing Legs"},
{name:"balance",label:"Balance"},
{name:"mic_drop",label:"Mic Drop"},
{name:"monster",label:"Monster"},
{name:"pose",label:"Pose"},
{name:"bow",label:"Bow"}
];
function initServos(){
const container=document.getElementById("servos");
servos.forEach(s=>{
const div=document.createElement("div");
div.className="servo-control";
const initialValue=s.ch<=2?(s.min+(s.max-s.min)/2):s.min;
div.innerHTML=`<div class="servo-label">CH${s.ch}: ${s.label}</div>
<div class="input-group">
<input type="range" class="servo-slider" id="slider${s.ch}" min="${s.min}" max="${s.max}" value="${initialValue}" oninput="updateServoValue(${s.ch})">
<span class="slider-value" id="value${s.ch}">${initialValue}</span>
<input type="number" id="speed${s.ch}" min="0.1" max="1.0" step="0.1" value="0.8" placeholder="Speed" style="width:60px">
<button onclick="moveServo(${s.ch})">Move</button>
</div>`;
container.appendChild(div);
});
}
function updateServoValue(ch){
const slider=document.getElementById("slider"+ch);
const display=document.getElementById("value"+ch);
display.textContent=slider.value;
}
function initPresets(){
const container=document.getElementById("presets");
presets.forEach(p=>{
const btn=document.createElement("button");
btn.className="preset-btn";
btn.textContent=p.label;
btn.onclick=()=>executePreset(p.name);
container.appendChild(btn);
});
}
function showMessage(msg,isError=false){
const msgEl=document.getElementById(isError?"error":"message");
const hideEl=document.getElementById(isError?"message":"error");
hideEl.style.display="none";
msgEl.textContent=msg;
msgEl.style.display="block";
setTimeout(()=>msgEl.style.display="none",3000);
}
async function moveServo(ch){
const target=parseInt(document.getElementById("slider"+ch).value);
const speed=parseFloat(document.getElementById("speed"+ch).value);
try{
const res=await fetch("/control",{
method:"POST",
headers:{"Content-Type":"application/json"},
body:JSON.stringify({type:"single",channel:ch,target:target,speed:speed,timestamp:Date.now()/1000})
});
const data=await res.json();
if(data.success){
showMessage(data.message);
}else{
showMessage(data.message||"Error",true);
}
}catch(e){
showMessage("Network error: "+e.message,true);
}
}
async function setSpeed(speed){
document.getElementById("globalSpeed").value=speed;
document.getElementById("speedDisplay").textContent=speed.toFixed(1);
try{
const res=await fetch("/control",{
method:"POST",
headers:{"Content-Type":"application/json"},
body:JSON.stringify({type:"speed",speed:speed})
});
const data=await res.json();
if(data.success){
showMessage("Global speed set to "+speed+"x");
}
}catch(e){
showMessage("Speed update failed: "+e.message,true);
}
}
async function updateGlobalSpeed(){
const speed=parseFloat(document.getElementById("globalSpeed").value);
document.getElementById("speedDisplay").textContent=speed.toFixed(1);
try{
const res=await fetch("/control",{
method:"POST",
headers:{"Content-Type":"application/json"},
body:JSON.stringify({type:"speed",speed:speed})
});
const data=await res.json();
if(data.success){
showMessage("Global speed set to "+speed+"x");
}
}catch(e){
showMessage("Speed update failed: "+e.message,true);
}
}
async function executePreset(name){
const repeat=parseInt(document.getElementById("presetRepeat").value)||1;
const delayMult=parseFloat(document.getElementById("presetDelay").value)||1.0;
const repeatText=repeat>1?" x"+repeat:"";
const delayText=delayMult!==1.0?" @"+delayMult.toFixed(1)+"x":"";
document.getElementById("status-indicator").textContent="Executing: "+name+repeatText+delayText+"...";
try{
const res=await fetch("/control",{
method:"POST",
headers:{"Content-Type":"application/json"},
body:JSON.stringify({type:"preset",preset:name,repeat:repeat,delay_multiplier:delayMult})
});
const data=await res.json();
if(data.success){
showMessage(data.message);
document.getElementById("status-indicator").textContent="";
}else{
showMessage(data.message||"Preset failed",true);
document.getElementById("status-indicator").textContent="";
}
}catch(e){
showMessage("Preset error: "+e.message,true);
document.getElementById("status-indicator").textContent="";
}
}
async function emergencyStop(){
if(!confirm("Emergency stop will disable all servos. Continue?")){return;}
try{
const res=await fetch("/emergency",{method:"POST"});
const data=await res.json();
showMessage("🚨 "+data.message);
}catch(e){
showMessage("Emergency stop error: "+e.message,true);
}
}
async function resume(){
try{
const res=await fetch("/resume",{method:"POST"});
const data=await res.json();
if(data.success){
showMessage(data.message);
}else{
showMessage(data.message||"Resume failed",true);
}
}catch(e){
showMessage("Resume error: "+e.message,true);
}
}
async function getStatus(){
try{
const res=await fetch("/status");
const data=await res.json();
if(data.success){
const d=data.data;
let html="<div class='status-item'><b>WiFi:</b> "+(d.wifi.connected?"Connected - IP: "+d.wifi.ip+" (RSSI: "+d.wifi.rssi+" dBm)":"Disconnected")+"</div>";
html+="<div class='status-item'><b>Hardware:</b> PCA9685 @ 0x40, 50Hz</div>";
html+="<div class='status-item'><b>Memory:</b> "+Math.round(d.memory.free/1024)+"KB free / "+Math.round(d.memory.total/1024)+"KB total</div>";
html+="<div class='status-item'><b>Uptime:</b> "+Math.round(d.uptime)+"s</div>";
html+="<div class='status-item'><b>Global Speed:</b> "+d.controller.global_speed+"</div>";
html+="<div class='status-item'><b>Emergency Stop:</b> "+(d.controller.emergency_stop?"ACTIVE":"Inactive")+"</div>";
html+="<div class='status-item'><b>Active Sequence:</b> "+(d.controller.active_sequence||"None")+"</div>";
document.getElementById("status").innerHTML=html;
}
}catch(e){
showMessage("Status fetch failed: "+e.message,true);
}
}
initServos();
initPresets();
setInterval(getStatus,5000);
getStatus();
</script>
</body>
</html>"""


async def handle_client(reader, writer, servo_controller, presets, boot_time):
    """
    Handle incoming HTTP client connection
    
    Args:
        reader: StreamReader for incoming data
        writer: StreamWriter for response
        servo_controller: ServoController instance
        presets: Dictionary of movement presets
        boot_time: System boot timestamp
    """
    try:
        # Read request line
        request_line = await reader.readline()
        request_line = request_line.decode('utf-8').strip()
        
        if not request_line:
            writer.close()
            await writer.wait_closed()
            return
        
        # Parse request
        parts = request_line.split(' ')
        if len(parts) < 2:
            writer.close()
            await writer.wait_closed()
            return
        
        method = parts[0]
        path = parts[1]
        
        # Read headers
        headers = {}
        while True:
            line = await reader.readline()
            line = line.decode('utf-8').strip()
            if not line:
                break
            if ':' in line:
                key, value = line.split(':', 1)
                headers[key.strip().lower()] = value.strip()
        
        # Read body for POST requests
        body = None
        if method == 'POST':
            content_length = int(headers.get('content-length', 0))
            if content_length > 0:
                body_bytes = await reader.read(content_length)
                body = body_bytes.decode('utf-8')
        
        # Route dispatch
        if path == '/' or path == '/index.html':
            await send_response(writer, 200, HTML_INTERFACE, 'text/html')
        
        elif path == '/control' and method == 'POST':
            await handle_control(writer, body, servo_controller, presets)
        
        elif path == '/status' and method == 'GET':
            await handle_status(writer, servo_controller, boot_time)
        
        elif path == '/emergency' and method == 'POST':
            await handle_emergency(writer, servo_controller)
        
        elif path == '/resume' and method == 'POST':
            await handle_resume(writer, servo_controller)
        
        elif path == '/config' and method == 'GET':
            await handle_get_config(writer)
        
        elif path == '/config/reload' and method == 'POST':
            await handle_reload_config(writer, servo_controller)
        
        else:
            await send_json_response(writer, 404, {
                "success": False,
                "message": "Not found",
                "error": f"Unknown route: {path}"
            })
        
    except Exception as e:
        print(f"Error handling client: {e}")
        try:
            await send_json_response(writer, 500, {
                "success": False,
                "message": "Internal server error",
                "error": str(e)
            })
        except:
            pass
    
    finally:
        try:
            writer.close()
            await writer.wait_closed()
        except:
            pass
        gc.collect()


async def handle_control(writer, body, servo_controller, presets):
    """Handle /control endpoint for servo commands"""
    try:
        # Parse JSON
        data = json.loads(body)
        cmd_type = data.get('type')
        
        if cmd_type == 'single':
            # Single servo movement
            channel = data.get('channel')
            target = data.get('target')
            speed = data.get('speed')
            
            # Validate
            from servo_config import validate_channel, validate_pulse_width, validate_speed
            validate_channel(channel)
            validate_pulse_width(channel, target)
            if speed is not None:
                validate_speed(speed)
            
            # Execute movement
            asyncio.create_task(servo_controller.move_servo_smooth(channel, target, speed))
            
            await send_json_response(writer, 200, {
                "success": True,
                "message": f"Servo {channel} moving to {target}",
                "server_timestamp": time.time()
            })
        
        elif cmd_type == 'speed':
            # Set global speed (0.1 to 10.0)
            speed = data.get('speed')
            if not isinstance(speed, (int, float)) or speed < 0.1 or speed > 10.0:
                raise ValueError(f"Speed must be between 0.1 and 10.0, got {speed}")
            
            servo_controller.global_speed = speed
            
            await send_json_response(writer, 200, {
                "success": True,
                "message": f"Global speed set to {speed}"
            })
        
        elif cmd_type == 'preset':
            # Execute preset sequence
            preset_name = data.get('preset')
            repeat = data.get('repeat', 1)  # Default to 1 if not specified
            delay_multiplier = data.get('delay_multiplier', 1.0)  # Default to 1.0
            
            if preset_name not in presets:
                await send_json_response(writer, 400, {
                    "success": False,
                    "message": f"Unknown preset: {preset_name}"
                })
                return
            
            # Validate repeat count
            if not isinstance(repeat, int) or repeat < 1 or repeat > 50:
                await send_json_response(writer, 400, {
                    "success": False,
                    "message": f"Repeat must be between 1 and 50, got {repeat}"
                })
                return
            
            # Validate delay multiplier
            if not isinstance(delay_multiplier, (int, float)) or delay_multiplier < 0.1 or delay_multiplier > 2.0:
                await send_json_response(writer, 400, {
                    "success": False,
                    "message": f"Delay multiplier must be between 0.1 and 2.0, got {delay_multiplier}"
                })
                return
            
            # Check if sequence already running
            if servo_controller.active_sequence is not None:
                await send_json_response(writer, 409, {
                    "success": False,
                    "message": f"Sequence already running: {servo_controller.active_sequence}"
                })
                return
            
            # Start preset execution
            asyncio.create_task(servo_controller.execute_preset(preset_name, presets, repeat, delay_multiplier))
            
            delay_info = f" @{delay_multiplier}x delay" if delay_multiplier != 1.0 else ""
            await send_json_response(writer, 200, {
                "success": True,
                "message": f"Preset '{preset_name}' started ({repeat} time{'s' if repeat > 1 else ''}){delay_info}"
            })
        
        elif cmd_type == 'multiple':
            # Multiple servo movement
            targets = data.get('targets', {})
            speed = data.get('speed')
            
            # Validate
            from servo_config import validate_targets
            validate_targets(targets)
            
            # Execute movement
            asyncio.create_task(servo_controller.move_multiple(targets, speed))
            
            await send_json_response(writer, 200, {
                "success": True,
                "message": f"Moving {len(targets)} servos"
            })
        
        else:
            await send_json_response(writer, 400, {
                "success": False,
                "message": f"Unknown command type: {cmd_type}"
            })
    
    except ValueError as e:
        await send_json_response(writer, 400, {
            "success": False,
            "message": "Validation error",
            "error": str(e)
        })
    except Exception as e:
        await send_json_response(writer, 500, {
            "success": False,
            "message": "Command failed",
            "error": str(e)
        })


async def handle_status(writer, servo_controller, boot_time):
    """Handle /status endpoint"""
    try:
        wifi_status = get_wifi_status()
        controller_status = servo_controller.get_status()
        
        status_data = {
            "wifi": wifi_status,
            "hardware": {
                "pca9685_detected": True,
                "i2c_address": "0x40",
                "pwm_frequency": "50Hz"
            },
            "memory": {
                "free": gc.mem_free(),
                "total": gc.mem_free() + gc.mem_alloc()
            },
            "uptime": time.time() - boot_time,
            "controller": {
                "global_speed": controller_status["global_speed"],
                "emergency_stop": controller_status["emergency_stop"],
                "active_sequence": controller_status["active_sequence"]
            }
        }
        
        await send_json_response(writer, 200, {
            "success": True,
            "data": status_data
        })
    
    except Exception as e:
        await send_json_response(writer, 500, {
            "success": False,
            "message": "Status fetch failed",
            "error": str(e)
        })


async def handle_emergency(writer, servo_controller):
    """Handle /emergency endpoint"""
    try:
        await servo_controller.emergency_stop_all()
        
        await send_json_response(writer, 200, {
            "success": True,
            "message": "Emergency stop activated - all servos disabled"
        })
    except Exception as e:
        await send_json_response(writer, 500, {
            "success": False,
            "message": "Emergency stop failed",
            "error": str(e)
        })


async def handle_resume(writer, servo_controller):
    """Handle /resume endpoint"""
    try:
        # Reset emergency stop flag
        servo_controller.emergency_stop = False
        
        # Re-initialize servos to neutral
        await servo_controller.initialize_servos()
        
        await send_json_response(writer, 200, {
            "success": True,
            "message": "Servos re-initialized to neutral positions"
        })
    except Exception as e:
        await send_json_response(writer, 500, {
            "success": False,
            "message": "Resume failed",
            "error": str(e)
        })


async def handle_get_config(writer):
    """Handle /config endpoint - return current servo configuration"""
    try:
        from servo_config import SERVO_CALIBRATION
        
        config_data = {}
        for channel in range(9):
            if channel in SERVO_CALIBRATION:
                servo = SERVO_CALIBRATION[channel]
                config_data[channel] = {
                    "min": servo["min"],
                    "max": servo["max"],
                    "neutral": servo["neutral"],
                    "label": servo["label"],
                    "reverse": servo.get("reverse", False)
                }
        
        await send_json_response(writer, 200, {
            "success": True,
            "config": config_data,
            "message": "Current servo configuration"
        })
    
    except Exception as e:
        await send_json_response(writer, 500, {
            "success": False,
            "message": "Failed to get configuration",
            "error": str(e)
        })


async def handle_reload_config(writer, servo_controller):
    """Handle /config/reload endpoint - reload config from INI file"""
    try:
        from servo_config import reload_config
        
        if reload_config():
            # Re-initialize servos with new config
            await servo_controller.initialize_servos()
            
            await send_json_response(writer, 200, {
                "success": True,
                "message": "Configuration reloaded from servo_config.ini and servos re-initialized"
            })
        else:
            await send_json_response(writer, 500, {
                "success": False,
                "message": "Failed to reload configuration file"
            })
    
    except Exception as e:
        await send_json_response(writer, 500, {
            "success": False,
            "message": "Config reload failed",
            "error": str(e)
        })


async def send_response(writer, status_code, body, content_type='text/plain'):
    """Send HTTP response"""
    status_text = {200: 'OK', 400: 'Bad Request', 404: 'Not Found', 
                   409: 'Conflict', 500: 'Internal Server Error', 503: 'Service Unavailable'}
    
    response = f"HTTP/1.1 {status_code} {status_text.get(status_code, 'Unknown')}\r\n"
    response += f"Content-Type: {content_type}\r\n"
    response += f"Content-Length: {len(body)}\r\n"
    response += "Connection: close\r\n"
    response += "\r\n"
    
    writer.write(response.encode('utf-8'))
    writer.write(body.encode('utf-8') if isinstance(body, str) else body)
    await writer.drain()


async def send_json_response(writer, status_code, data):
    """Send JSON response"""
    body = json.dumps(data)
    await send_response(writer, status_code, body, 'application/json')


async def start_server(servo_controller, port=80):
    """
    Start the web server
    
    Args:
        servo_controller: ServoController instance
        port: TCP port to listen on (default 80)
    """
    # Import presets (will create this file later)
    try:
        from movement_presets import PRESETS
        presets = PRESETS
    except ImportError:
        print("Warning: movement_presets.py not found, presets disabled")
        presets = {}
    
    # Get boot time
    boot_time = time.time()
    
    print(f"Starting web server on port {port}...")
    
    server = await asyncio.start_server(
        lambda r, w: handle_client(r, w, servo_controller, presets, boot_time),
        "0.0.0.0",
        port
    )
    
    print(f"Web server listening on port {port}")
    
    async with server:
        await server.wait_closed()
