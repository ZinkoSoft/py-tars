"""Config Manager Service - Core business logic."""

from __future__ import annotations

import asyncio
import logging
from typing import Optional

from tars.config.cache import LKGCacheManager
from tars.config.database import ConfigDatabase

from .auth import initialize_token_store
from .config import ConfigManagerConfig
from .mqtt import MQTTPublisher

logger = logging.getLogger(__name__)


class ConfigManagerService:
    """Core service for centralized configuration management.

    Responsibilities:
    - Initialize and maintain configuration database
    - Manage last-known-good cache
    - Provide configuration CRUD operations
    - Publish configuration updates via MQTT
    - Monitor health and report status
    """

    def __init__(self, config: ConfigManagerConfig):
        """Initialize config manager service.

        Args:
            config: Service configuration
        """
        self.config = config
        self.database: Optional[ConfigDatabase] = None
        self.cache_manager: Optional[LKGCacheManager] = None
        self.mqtt_publisher: Optional[MQTTPublisher] = None
        self._healthy = False
        self._shutdown_event = asyncio.Event()

    async def initialize(self) -> None:
        """Initialize database and cache manager.

        Raises:
            RuntimeError: If initialization fails
        """
        logger.info("Initializing config manager service")

        try:
            # Initialize token store for API authentication
            logger.info("Initializing API token store")
            token_store = initialize_token_store()
            logger.info(f"Token store initialized with {len(token_store._tokens)} tokens")
            
            # Initialize database
            logger.info(f"Opening database: {self.config.db_path}")
            self.database = ConfigDatabase(str(self.config.db_path))
            await self.database.connect()
            await self.database.initialize_schema()

            # Initialize cache manager
            logger.info(f"Initializing LKG cache: {self.config.lkg_cache_path}")
            self.cache_manager = LKGCacheManager(
                cache_path=str(self.config.lkg_cache_path),
                hmac_key_base64=self.config.hmac_key_base64,
            )

            # Initialize database with default service configs if empty
            logger.info("Checking database for existing services")
            services = await self.database.list_services()
            
            if not services:
                logger.info("Database is empty, initializing with default service configs")
                await self._initialize_default_configs()
                services = await self.database.list_services()
                logger.info(f"Initialized {len(services)} services with default configurations")
            
            # Sync cache with database
            logger.info("Syncing LKG cache with database")
            service_configs = {}
            config_epoch = None
            
            for service_name in services:
                config_data = await self.database.get_service_config(service_name)
                if config_data:
                    service_configs[service_name] = config_data.config
                    # Get epoch from first service (all have same epoch)
                    if config_epoch is None:
                        config_epoch = config_data.config_epoch
            
            # If no epoch exists, create one
            if config_epoch is None:
                config_epoch = await self.database.create_epoch()
                logger.info(f"Created initial config epoch: {config_epoch}")
            
            # Update cache
            await self.cache_manager.atomic_update_from_db(
                service_configs, config_epoch
            )
            logger.info(f"LKG cache synced with {len(service_configs)} services")

            # Initialize MQTT publisher
            logger.info("Connecting to MQTT broker")
            self.mqtt_publisher = MQTTPublisher(self.config)
            await self.mqtt_publisher.connect()

            self._healthy = True
            logger.info("Config manager service initialized successfully")

        except Exception as e:
            logger.error(f"Failed to initialize config manager: {e}", exc_info=True)
            self._healthy = False
            raise RuntimeError(f"Config manager initialization failed: {e}") from e

    async def health_check(self) -> dict[str, any]:
        """Perform health check.

        Returns:
            Health status dictionary with ok, database_available, cache_available
        """
        db_available = False
        cache_available = False

        if self.database:
            try:
                # Simple database query to verify connectivity
                await self.database.list_services()
                db_available = True
            except Exception as e:
                logger.warning(f"Database health check failed: {e}")

        if self.cache_manager:
            try:
                # Verify cache file is readable
                cache_available = self.config.lkg_cache_path.exists()
            except Exception as e:
                logger.warning(f"Cache health check failed: {e}")

        self._healthy = db_available and cache_available

        return {
            "ok": self._healthy,
            "database_available": db_available,
            "cache_available": cache_available,
            "db_path": str(self.config.db_path),
            "cache_path": str(self.config.lkg_cache_path),
        }

    async def shutdown(self) -> None:
        """Gracefully shutdown the service."""
        logger.info("Shutting down config manager service")
        self._shutdown_event.set()

        # Disconnect MQTT
        if self.mqtt_publisher:
            try:
                await self.mqtt_publisher.disconnect()
                logger.info("MQTT disconnected")
            except Exception as e:
                logger.error(f"Error disconnecting MQTT: {e}", exc_info=True)

        # Close database connection
        if self.database:
            try:
                await self.database.close()
                logger.info("Database connection closed")
            except Exception as e:
                logger.error(f"Error closing database: {e}", exc_info=True)

        self._healthy = False
        logger.info("Config manager service shutdown complete")

    async def _initialize_default_configs(self) -> None:
        """Initialize database with default service configurations.

        Creates service_configs entries with default values from Pydantic models
        and syncs config_items table with field metadata.
        """
        from tars.config.metadata import (
            create_default_service_configs,
            extract_field_metadata,
            get_all_service_configs,
        )

        if not self.database:
            raise RuntimeError("Database not initialized")

        # Get all service config models
        all_configs = get_all_service_configs()
        default_configs = create_default_service_configs()

        # Get current epoch or create one
        try:
            epoch = await self.database.get_config_epoch()
            config_epoch = epoch.config_epoch if epoch else await self.database.create_epoch()
        except Exception:
            # No epoch exists, create one
            config_epoch = await self.database.create_epoch()

        # Insert each service config
        for service_name, config_dict in default_configs.items():
            logger.info(f"Initializing {service_name} with default configuration")

            # Insert service config
            await self.database.update_service_config(
                service=service_name, config=config_dict, expected_version=None
            )

            # Extract metadata and sync config_items
            config_model = all_configs[service_name]
            metadata = extract_field_metadata(config_model)
            await self.database.sync_config_items(service_name, config_dict, metadata)

    @property
    def is_healthy(self) -> bool:
        """Check if service is healthy."""
        return self._healthy

    async def wait_for_shutdown(self) -> None:
        """Wait for shutdown signal."""
        await self._shutdown_event.wait()
