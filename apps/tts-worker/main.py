import asyncio, os, tempfile, subprocess, logging, time
import orjson as json
import asyncio_mqtt as mqtt
from urllib.parse import urlparse

# Configure logging
logging.basicConfig(
    level=os.getenv("LOG_LEVEL", "INFO"),
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S"
)
logger = logging.getLogger("tts-worker")

MQTT_URL = os.getenv("MQTT_URL", "mqtt://tars:pass@127.0.0.1:1883")
VOICE = os.getenv("PIPER_VOICE", "/voices/TARS.onnx")

def piper_cmd(text: str, wav_path: str) -> list[str]:
    # For pip-installed piper-tts: use stdin for text input
    return ["piper", "-m", VOICE, "-f", wav_path]

async def speak(text: str, mqtt_client=None):
    if mqtt_client:
        # Notify STT that TTS is starting
        status_msg = json.dumps({
            'event': 'speaking_start', 
            'text': text, 
            'timestamp': time.time()
        })
        await mqtt_client.publish('tts/status', status_msg)
        logger.info(f"Published TTS start status: {status_msg}")
    
    try:
        with tempfile.NamedTemporaryFile(suffix='.wav', delete=True) as f:
            # Pass text via stdin instead of command line argument
            logger.debug(f"Generating audio with Piper: {f.name}")
            subprocess.run(piper_cmd(text, f.name), input=text, text=True, check=True)
            logger.debug(f"Playing audio with paplay: {f.name}")
            # Try paplay first (PulseAudio), fall back to aplay if not available
            try:
                subprocess.run(['paplay', f.name], check=True)
            except FileNotFoundError:
                logger.warning("paplay not found, falling back to aplay")
                subprocess.run(['aplay', f.name], check=True)
    finally:
        if mqtt_client:
            # Notify STT that TTS has finished
            status_msg = json.dumps({
                'event': 'speaking_end', 
                'text': text, 
                'timestamp': time.time()
            })
            await mqtt_client.publish('tts/status', status_msg)
            logger.info(f"Published TTS end status: {status_msg}")

def parse_mqtt(url: str):
    u = urlparse(url)
    username = u.username
    password = u.password
    host = u.hostname or '127.0.0.1'
    port = u.port or 1883
    return host, port, username, password

async def main():
    host, port, username, password = parse_mqtt(MQTT_URL)
    logger.info(f"Connecting to MQTT {host}:{port}")
    async with mqtt.Client(hostname=host, port=port, username=username, password=password, client_id='tars-tts') as client:
        logger.info(f"Connected to MQTT {host}:{port} as tars-tts")
        await client.publish('system/health/tts', json.dumps({'ok': True, 'event': 'ready'}))
        await client.subscribe('tts/say')
        logger.info("Subscribed to tts/say, ready to process messages")
        async with client.messages() as messages:
            async for msg in messages:
                try:
                    data = json.loads(msg.payload)
                    text = data.get('text', '')
                    if text.strip():
                        logger.info(f"Speaking: {text[:80]}{'...' if len(text) > 80 else ''}")
                        await speak(text, client)
                    else:
                        logger.warning("Received empty text message")
                except Exception as e:
                    logger.error(f"Error processing message: {e}")
                    await client.publish('system/health/tts', json.dumps({'ok': False, 'err': str(e)}))

if __name__ == '__main__':
    asyncio.run(main())
