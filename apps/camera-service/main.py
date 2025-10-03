#!/usr/bin/env python3
"""
Camera Service for TARS

Captures video from camera and provides MJPEG streaming over HTTP.
Publishes occasional frames to MQTT for monitoring/debugging.
Optimized for mobile robot use cases with configurable frame rates and quality.
"""
import sys

# Add system dist-packages to path for libcamera BEFORE any imports that use it
sys.path.insert(0, '/usr/lib/python3/dist-packages')

import asyncio
import logging
import signal

from config import load_config
from service import CameraService


def main():
    """Main entry point."""
    cfg = load_config()
    
    # Configure logging
    logging.basicConfig(
        level=cfg.log_level,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    )
    
    # Check if camera is enabled
    if not cfg.enabled:
        logging.info("Camera service is disabled via CAMERA_ENABLED config. Exiting.")
        return
    
    service = CameraService(cfg)

    def signal_handler(signum, frame):
        logging.info(f"Received signal {signum}, shutting down...")
        service.stop()

    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)

    try:
        asyncio.run(service.start())
    except KeyboardInterrupt:
        pass
    finally:
        service.stop()


if __name__ == "__main__":
    main()