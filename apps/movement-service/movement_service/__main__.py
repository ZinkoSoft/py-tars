from __future__ import annotations

import asyncio
import logging

from movement_service.calibration import MovementCalibration
from movement_service.config import MovementSettings
from movement_service.service import MovementService


def configure_logging(level: str | None = None) -> None:
    logging.basicConfig(
        level=getattr(logging, (level or "INFO").upper(), logging.INFO),
        format="%(asctime)s %(name)s %(levelname)s %(message)s",
    )


def main() -> None:
    configure_logging()
    settings = MovementSettings.from_env()
    calibration = MovementCalibration.load(settings.calibration_path)
    service = MovementService(settings, calibration=calibration)
    asyncio.run(service.run())


if __name__ == "__main__":
    main()
