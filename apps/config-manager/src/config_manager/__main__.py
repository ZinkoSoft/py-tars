"""Config Manager Service - Entry point."""

from __future__ import annotations

import asyncio
import logging
import signal
import sys
from contextlib import asynccontextmanager

import uvicorn
from fastapi import FastAPI

from .api import router as config_router
from .config import load_config
from .service import ConfigManagerService

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
)
logger = logging.getLogger(__name__)

# Global service instance
service: ConfigManagerService | None = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    """FastAPI lifespan context manager.

    Handles startup and shutdown of the config manager service.
    """
    global service

    # Load configuration
    config = load_config()
    logger.info(f"Loaded configuration: log_level={config.log_level}")

    # Set log level
    logging.getLogger().setLevel(config.log_level)

    # Initialize service (assign to global)
    global service
    service = ConfigManagerService(config)

    try:
        await service.initialize()
        logger.info("Config manager service started")
        yield
    except Exception as e:
        logger.error(f"Failed to start config manager: {e}", exc_info=True)
        sys.exit(1)
    finally:
        # Shutdown
        if service:
            await service.shutdown()
            logger.info("Config manager service stopped")
            service = None


def create_app() -> FastAPI:
    """Create FastAPI application.

    Returns:
        FastAPI application instance
    """
    app = FastAPI(
        title="TARS Config Manager",
        description="Centralized configuration management for TARS voice assistant",
        version="0.1.0",
        lifespan=lifespan,
    )

    # Include API router
    app.include_router(config_router)

    # Health check endpoint
    @app.get("/health")
    async def health():
        """Health check endpoint."""
        if not service:
            return {"ok": False, "error": "Service not initialized"}
        return await service.health_check()

    return app


def main() -> None:
    """Main entry point."""
    config = load_config()

    # Create FastAPI app
    app = create_app()

    # Run server
    logger.info(
        f"Starting config manager API server on {config.api_host}:{config.api_port}"
    )
    uvicorn.run(
        app,
        host=config.api_host,
        port=config.api_port,
        reload=config.api_reload,
        log_level=config.log_level.lower(),
    )


if __name__ == "__main__":
    main()
