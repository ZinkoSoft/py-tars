import asyncio
import logging
from tts_worker.config import LOG_LEVEL, PIPER_VOICE
from tts_worker.piper_synth import PiperSynth
from tts_worker.service import TTSService


def setup_logging():
    logging.basicConfig(
        level=LOG_LEVEL,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )


async def main():
    setup_logging()
    synth = PiperSynth(PIPER_VOICE)
    service = TTSService(synth)
    await service.run()


if __name__ == "__main__":
    asyncio.run(main())
