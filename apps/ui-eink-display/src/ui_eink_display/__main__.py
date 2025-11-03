"""
Main entry point for UI E-Ink Display service.

Initializes and runs the display service with MQTT integration.
"""

import asyncio
import logging
import signal
import sys
from pathlib import Path

from .config import DisplayConfig
from .display_manager import DisplayManager
from .display_state import DisplayMode, DisplayState
from .mqtt_handler import MQTTHandler


def setup_logging(log_level: str) -> None:
    """
    Configure logging for the service.

    Args:
        log_level: Logging level (DEBUG, INFO, WARNING, ERROR)
    """
    logging.basicConfig(
        level=log_level,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        handlers=[logging.StreamHandler(sys.stdout)],
    )


async def main() -> None:
    """Main service loop."""
    # Load configuration
    try:
        config = DisplayConfig.from_env()
    except ValueError as e:
        print(f"Configuration error: {e}", file=sys.stderr)
        sys.exit(1)

    # Setup logging
    setup_logging(config.log_level)
    logger = logging.getLogger(__name__)
    logger.info("Starting UI E-Ink Display service")
    logger.info(f"Configuration: mock={config.mock_display}, timeout={config.display_timeout_sec}s")

    # Setup PYTHONPATH for waveshare library
    config.setup_pythonpath()

    # Initialize components
    state = DisplayState(mode=DisplayMode.STANDBY)
    display_manager = DisplayManager(
        mock=config.mock_display,
        font_path=config.font_path,
    )
    mqtt_handler = MQTTHandler(config, state, display_manager)

    # Shutdown handler
    shutdown_event = asyncio.Event()

    def signal_handler(sig, frame):
        logger.info(f"Received signal {sig}, shutting down...")
        shutdown_event.set()

    # Register signal handlers
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)

    try:
        # Initialize display hardware
        logger.info("Initializing display hardware...")
        await display_manager.initialize()

        # Render initial standby screen
        logger.info("Rendering standby screen...")
        await display_manager.render(state)

        # Start MQTT handler
        logger.info("Starting MQTT handler...")
        mqtt_task = asyncio.create_task(mqtt_handler.start())

        # Wait for shutdown signal
        await shutdown_event.wait()

        # Shutdown
        logger.info("Shutting down...")
        await mqtt_handler.stop()

        # Wait for MQTT task to complete (with timeout)
        try:
            await asyncio.wait_for(mqtt_task, timeout=5.0)
        except asyncio.TimeoutError:
            logger.warning("MQTT handler shutdown timeout, cancelling...")
            mqtt_task.cancel()
            try:
                await mqtt_task
            except asyncio.CancelledError:
                pass

        # Shutdown display
        await display_manager.shutdown()

        logger.info("Service stopped successfully")

    except Exception as e:
        logger.error(f"Fatal error: {e}", exc_info=True)
        sys.exit(1)


def run() -> None:
    """Entry point for the service."""
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\nInterrupted by user")
        sys.exit(0)


if __name__ == "__main__":
    run()
