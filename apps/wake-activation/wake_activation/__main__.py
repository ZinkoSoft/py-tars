from __future__ import annotations

import asyncio
import signal

from .config import WakeActivationConfig
from .service import WakeActivationService


async def main() -> None:
    config = WakeActivationConfig()
    service = WakeActivationService(config)

    loop = asyncio.get_running_loop()
    stop_event = asyncio.Event()

    def _handle_stop(_: signal.Signals) -> None:
        stop_event.set()

    for sig in (signal.SIGINT, signal.SIGTERM):
        loop.add_signal_handler(sig, _handle_stop, sig)

    await asyncio.gather(service.run(), stop_event.wait())


if __name__ == "__main__":
    asyncio.run(main())
