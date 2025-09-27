import asyncio
import logging
from tts_worker.config import (
    LOG_LEVEL,
    PIPER_VOICE,
    TTS_PROVIDER,
    ELEVEN_API_BASE,
    ELEVEN_API_KEY,
    ELEVEN_VOICE_ID,
    ELEVEN_MODEL_ID,
    ELEVEN_OPTIMIZE_STREAMING,
)
from tts_worker.piper_synth import PiperSynth
from tts_worker.service import TTSService
from external_services.eleven_labs import ElevenLabsTTS


def setup_logging():
    logging.basicConfig(
        level=LOG_LEVEL,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )


async def main():
    setup_logging()
    piper_synth: PiperSynth | None = None
    try:
        try:
            piper_synth = PiperSynth(PIPER_VOICE)
        except Exception:
            logging.exception("Failed to initialize Piper voice '%s'", PIPER_VOICE)
            piper_synth = None

        if TTS_PROVIDER == "elevenlabs":
            if not ELEVEN_API_KEY or not ELEVEN_VOICE_ID:
                logging.warning("TTS_PROVIDER=elevenlabs but ELEVEN_API_KEY or ELEVEN_VOICE_ID is missing; falling back to Piper")
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
                logging.warning("Piper voice unavailable; wake acknowledgements will use ElevenLabs provider")
        else:
            if piper_synth is None:
                piper_synth = PiperSynth(PIPER_VOICE)
            synth = piper_synth
            wake_synth = None
    except Exception:
        logging.exception("Failed to initialize TTS provider '%s'; falling back to Piper", TTS_PROVIDER)
        piper_synth = piper_synth or PiperSynth(PIPER_VOICE)
        synth = piper_synth
        wake_synth = None

    service = TTSService(synth, wake_ack_synth=wake_synth)
    await service.run()


if __name__ == "__main__":
    asyncio.run(main())
