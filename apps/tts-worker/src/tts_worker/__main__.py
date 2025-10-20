from __future__ import annotations

import asyncio
import logging

from .config import (
    LOG_LEVEL,
    PIPER_VOICE,
    TTS_PROVIDER,
    ELEVEN_API_BASE,
    ELEVEN_API_KEY,
    ELEVEN_VOICE_ID,
    ELEVEN_MODEL_ID,
    ELEVEN_OPTIMIZE_STREAMING,
    MQTT_URL,
)
from .piper_synth import PiperSynth
from .service import TTSService
from external_services.eleven_labs import ElevenLabsTTS
from . import config_lib_adapter


def _setup_logging() -> None:
    logging.basicConfig(
        level=LOG_LEVEL,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )


def _build_service() -> tuple[TTSService, PiperSynth | None]:
    piper_synth: PiperSynth | None = None
    try:
        piper_synth = PiperSynth(PIPER_VOICE)
    except Exception:
        logging.exception("Failed to initialize Piper voice '%s'", PIPER_VOICE)
        piper_synth = None

    if TTS_PROVIDER == "elevenlabs":
        if not ELEVEN_API_KEY or not ELEVEN_VOICE_ID:
            logging.warning(
                "TTS_PROVIDER=elevenlabs but ELEVEN_API_KEY or ELEVEN_VOICE_ID is missing; falling back to Piper",
            )
            raise ValueError("missing-eleven-envs")
        synth = ElevenLabsTTS(
            api_key=ELEVEN_API_KEY,
            voice_id=ELEVEN_VOICE_ID,
            api_base=ELEVEN_API_BASE,
            model_id=ELEVEN_MODEL_ID,
            optimize_streaming=ELEVEN_OPTIMIZE_STREAMING,
        )
        wake_synth = piper_synth
        if wake_synth is None:
            logging.warning(
                "Piper voice unavailable; wake acknowledgements will use ElevenLabs provider",
            )
    else:
        if piper_synth is None:
            piper_synth = PiperSynth(PIPER_VOICE)
        synth = piper_synth
        wake_synth = None

    service = TTSService(synth, wake_ack_synth=wake_synth)
    return service, piper_synth


async def _async_main() -> None:
    _setup_logging()
    
    # Initialize config library and subscribe to MQTT updates
    try:
        await config_lib_adapter.initialize_and_subscribe(mqtt_url=MQTT_URL)
        logging.info("Config library initialized - will receive MQTT updates")
    except Exception as e:
        logging.warning("Failed to initialize config library: %s - using env vars only", e)
    
    service: TTSService
    fallback: PiperSynth | None = None
    try:
        service, fallback = _build_service()
    except Exception:
        logging.exception(
            "Failed to initialize TTS provider '%s'; falling back to Piper", TTS_PROVIDER
        )
        final_synth = fallback or PiperSynth(PIPER_VOICE)
        service = TTSService(final_synth)
    
    try:
        await service.run()
    finally:
        # Clean up config library on shutdown
        await config_lib_adapter.close()


def main() -> None:
    """Run the TTS worker."""

    asyncio.run(_async_main())


if __name__ == "__main__":  # pragma: no cover - module entry point
    main()
