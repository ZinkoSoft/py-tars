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
    "config_path": "movement_config.json",
}


def load_config(path):
    try:
        with open(path, "r", encoding="utf-8") as fp:  # type: ignore
            user_cfg = json.loads(fp.read())
    except OSError:
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
        self._client = None
        self._pwm = None
        self._last_frame_at = ticks_ms()
        self._positions = {}
        led_pin = config.get("status_led")
        if Pin is not None and led_pin is not None:
            self._led = Pin(led_pin, Pin.OUT)
        else:
            self._led = None

    def connect_wifi(self):
        if network is None:
            return
        station = network.WLAN(network.STA_IF)
        station.active(True)
        wifi_cfg = self.config["wifi"]
        if not station.isconnected():
            station.connect(wifi_cfg.get("ssid"), wifi_cfg.get("password"))
            retries = 0
            while not station.isconnected():
                sleep_ms(200)
                retries += 1
                if retries > 100:
                    raise RuntimeError("Wi-Fi connection timeout")

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
            if self._led is not None:
                self._led.value(0 if self._led.value() else 1)
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