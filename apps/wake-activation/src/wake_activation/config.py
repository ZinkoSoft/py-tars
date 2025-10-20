from __future__ import annotations

import os
from collections.abc import Mapping, MutableMapping
from dataclasses import dataclass, field
from pathlib import Path

from tars.contracts.v1 import (  # type: ignore[import]
    TOPIC_STT_FINAL,
    TOPIC_TTS_CONTROL,
    TOPIC_TTS_STATUS,
    TOPIC_WAKE_EVENT,
    TOPIC_WAKE_MIC,
)


@dataclass(slots=True)
class WakeActivationConfig:
    """Typed configuration for the wake activation service."""

    mqtt_url: str = field(
        default_factory=lambda: os.getenv("MQTT_URL", "mqtt://tars:pass@127.0.0.1:1883")
    )
    audio_fanout_path: Path = field(
        default_factory=lambda: Path(os.getenv("WAKE_AUDIO_FANOUT", "/tmp/tars/audio-fanout.sock"))
    )
    wake_model_path: Path = field(
        default_factory=lambda: Path(
            os.getenv("WAKE_MODEL_PATH", "/models/openwakeword/hey_tars.tflite")
        )
    )
    wake_detection_threshold: float = field(
        default_factory=lambda: float(os.getenv("WAKE_DETECTION_THRESHOLD", "0.55"))
    )
    min_retrigger_sec: float = field(
        default_factory=lambda: float(os.getenv("WAKE_MIN_RETRIGGER_SEC", "1.0"))
    )
    interrupt_window_sec: float = field(
        default_factory=lambda: float(os.getenv("WAKE_INTERRUPT_WINDOW_SEC", "2.5"))
    )
    idle_timeout_sec: float = field(
        default_factory=lambda: float(os.getenv("WAKE_IDLE_TIMEOUT_SEC", "3.0"))
    )
    health_topic: str = field(default_factory=lambda: os.getenv("WAKE_HEALTH_TOPIC", "system/health/wake-activation"))
    wake_event_topic: str = field(
        default_factory=lambda: os.getenv("WAKE_EVENT_TOPIC", TOPIC_WAKE_EVENT)
    )
    mic_control_topic: str = field(
        default_factory=lambda: os.getenv("WAKE_MIC_TOPIC", TOPIC_WAKE_MIC)
    )
    tts_control_topic: str = field(
        default_factory=lambda: os.getenv("WAKE_TTS_TOPIC", TOPIC_TTS_CONTROL)
    )
    tts_status_topic: str = field(
        default_factory=lambda: os.getenv("WAKE_TTS_STATUS_TOPIC", TOPIC_TTS_STATUS)
    )
    stt_final_topic: str = field(
        default_factory=lambda: os.getenv("WAKE_STT_FINAL_TOPIC", TOPIC_STT_FINAL)
    )
    detection_window_ms: int = field(
        default_factory=lambda: int(os.getenv("WAKE_DETECTION_WINDOW_MS", "750"))
    )
    health_interval_sec: float = field(
        default_factory=lambda: float(os.getenv("WAKE_HEALTH_INTERVAL_SEC", "15"))
    )
    log_level: str = field(default_factory=lambda: os.getenv("LOG_LEVEL", "INFO"))
    enable_speex_noise_suppression: bool = field(
        default_factory=lambda: os.getenv("WAKE_SPEEX_NOISE_SUPPRESSION", "0").lower()
        in {"1", "true", "yes"}
    )
    vad_threshold: float = field(
        default_factory=lambda: float(os.getenv("WAKE_VAD_THRESHOLD", "0.0"))
    )

    # Advanced sensitivity settings
    energy_boost_factor: float = field(
        default_factory=lambda: float(os.getenv("WAKE_ENERGY_BOOST_FACTOR", "1.0"))
    )
    low_energy_threshold_factor: float = field(
        default_factory=lambda: float(os.getenv("WAKE_LOW_ENERGY_THRESHOLD_FACTOR", "0.8"))
    )
    background_noise_sensitivity: bool = field(
        default_factory=lambda: os.getenv("WAKE_BACKGROUND_NOISE_SENSITIVITY", "0").lower()
        in {"1", "true", "yes"}
    )

    # Health monitoring
    stt_health_topic: str = field(
        default_factory=lambda: os.getenv("WAKE_STT_HEALTH_TOPIC", "system/health/tars-stt")
    )
    wait_for_stt_health: bool = field(
        default_factory=lambda: os.getenv("WAKE_WAIT_FOR_STT_HEALTH", "1").lower()
        in {"1", "true", "yes"}
    )
    stt_health_timeout_sec: float = field(
        default_factory=lambda: float(os.getenv("WAKE_STT_HEALTH_TIMEOUT_SEC", "30"))
    )

    # NPU acceleration settings
    use_npu: bool = field(
        default_factory=lambda: os.getenv("WAKE_USE_NPU", "0").lower() in {"1", "true", "yes"}
    )
    rknn_model_path: Path = field(
        default_factory=lambda: Path(
            os.getenv("WAKE_RKNN_MODEL_PATH", "/models/openwakeword/hey_tars.rknn")
        )
    )
    npu_core_mask: int = field(default_factory=lambda: int(os.getenv("WAKE_NPU_CORE_MASK", "0")))

    @classmethod
    def from_env(cls, env: Mapping[str, str] | None = None) -> WakeActivationConfig:
        """Create a configuration instance from a mapping (defaults to os.environ)."""

        if env is None:
            return cls()

        # For testability allow passing an explicit mapping; convert to mutable copy for pop().
        data: MutableMapping[str, str] = dict(env)

        def _pop(key: str, default: str) -> str:
            return data.pop(key, default)

        config = cls(
            mqtt_url=_pop("MQTT_URL", cls().mqtt_url),
            audio_fanout_path=Path(_pop("WAKE_AUDIO_FANOUT", str(cls().audio_fanout_path))),
            wake_model_path=Path(_pop("WAKE_MODEL_PATH", str(cls().wake_model_path))),
            wake_detection_threshold=float(
                _pop("WAKE_DETECTION_THRESHOLD", str(cls().wake_detection_threshold))
            ),
            min_retrigger_sec=float(_pop("WAKE_MIN_RETRIGGER_SEC", str(cls().min_retrigger_sec))),
            interrupt_window_sec=float(
                _pop("WAKE_INTERRUPT_WINDOW_SEC", str(cls().interrupt_window_sec))
            ),
            idle_timeout_sec=float(_pop("WAKE_IDLE_TIMEOUT_SEC", str(cls().idle_timeout_sec))),
            health_topic=_pop("WAKE_HEALTH_TOPIC", cls().health_topic),
            wake_event_topic=_pop("WAKE_EVENT_TOPIC", cls().wake_event_topic),
            mic_control_topic=_pop("WAKE_MIC_TOPIC", cls().mic_control_topic),
            tts_control_topic=_pop("WAKE_TTS_TOPIC", cls().tts_control_topic),
            tts_status_topic=_pop("WAKE_TTS_STATUS_TOPIC", cls().tts_status_topic),
            stt_final_topic=_pop("WAKE_STT_FINAL_TOPIC", cls().stt_final_topic),
            detection_window_ms=int(
                _pop("WAKE_DETECTION_WINDOW_MS", str(cls().detection_window_ms))
            ),
            health_interval_sec=float(
                _pop("WAKE_HEALTH_INTERVAL_SEC", str(cls().health_interval_sec))
            ),
            log_level=_pop("LOG_LEVEL", cls().log_level),
            enable_speex_noise_suppression=_pop(
                "WAKE_SPEEX_NOISE_SUPPRESSION",
                "1" if cls().enable_speex_noise_suppression else "0",
            ).lower()
            in {"1", "true", "yes"},
            vad_threshold=float(_pop("WAKE_VAD_THRESHOLD", str(cls().vad_threshold))),
            energy_boost_factor=float(
                _pop("WAKE_ENERGY_BOOST_FACTOR", str(cls().energy_boost_factor))
            ),
            low_energy_threshold_factor=float(
                _pop("WAKE_LOW_ENERGY_THRESHOLD_FACTOR", str(cls().low_energy_threshold_factor))
            ),
            background_noise_sensitivity=_pop(
                "WAKE_BACKGROUND_NOISE_SENSITIVITY",
                "1" if cls().background_noise_sensitivity else "0",
            ).lower()
            in {"1", "true", "yes"},
            stt_health_topic=_pop("WAKE_STT_HEALTH_TOPIC", cls().stt_health_topic),
            wait_for_stt_health=_pop(
                "WAKE_WAIT_FOR_STT_HEALTH",
                "1" if cls().wait_for_stt_health else "0",
            ).lower()
            in {"1", "true", "yes"},
            stt_health_timeout_sec=float(
                _pop("WAKE_STT_HEALTH_TIMEOUT_SEC", str(cls().stt_health_timeout_sec))
            ),
            use_npu=_pop("WAKE_USE_NPU", "1" if cls().use_npu else "0").lower()
            in {"1", "true", "yes"},
            rknn_model_path=Path(_pop("WAKE_RKNN_MODEL_PATH", str(cls().rknn_model_path))),
            npu_core_mask=int(_pop("WAKE_NPU_CORE_MASK", str(cls().npu_core_mask))),
        )
        if data:
            unknown = ", ".join(sorted(data))
            raise ValueError(f"Unknown wake activation config keys: {unknown}")
        return config
