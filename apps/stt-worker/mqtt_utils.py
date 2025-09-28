"""Compatibility shim re-exporting the packaged MQTT client wrapper."""

from stt_worker.mqtt_utils import MQTTClientWrapper

__all__ = ["MQTTClientWrapper"]
