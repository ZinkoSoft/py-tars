"""Last-known-good (LKG) cache management for configuration fallback.

Provides:
- HMAC-signed cache writing and reading
- Atomic cache updates (within 100ms of DB read)
- Tamper detection via signature verification
- Read-only fallback when database unavailable
"""

from __future__ import annotations

import asyncio
from datetime import datetime
from pathlib import Path
from typing import Any

import orjson

from tars.config.crypto import sign_cache_async, verify_cache_async
from tars.config.models import LKGCache


class LKGCacheManager:
    """Manager for last-known-good configuration cache."""

    def __init__(self, cache_path: str | Path, hmac_key_base64: str):
        """Initialize cache manager.

        Args:
            cache_path: Path to cache file
            hmac_key_base64: Base64-encoded HMAC key for signing
        """
        self.cache_path = Path(cache_path)
        self.hmac_key_base64 = hmac_key_base64
        self._write_lock = asyncio.Lock()

    async def write_lkg_cache(
        self, service_configs: dict[str, dict[str, Any]], config_epoch: str
    ) -> None:
        """Write last-known-good cache with HMAC signature.

        Args:
            service_configs: Service -> config mapping
            config_epoch: Current database epoch

        Raises:
            IOError: If cache file cannot be written
        """
        async with self._write_lock:
            # Create signed cache structure
            cache_data = {
                "payload": service_configs,
                "config_epoch": config_epoch,
                "generated_at": datetime.utcnow().isoformat(),
            }

            # Sign cache with HMAC
            signed_cache = await sign_cache_async(cache_data, self.hmac_key_base64)

            # Write atomically: write to temp file, then rename
            temp_path = self.cache_path.with_suffix(".tmp")
            self.cache_path.parent.mkdir(parents=True, exist_ok=True)

            # Use orjson for fast serialization
            cache_json = orjson.dumps(
                signed_cache,
                option=orjson.OPT_INDENT_2 | orjson.OPT_SORT_KEYS | orjson.OPT_UTC_Z,
            )

            await asyncio.to_thread(temp_path.write_bytes, cache_json)
            await asyncio.to_thread(temp_path.replace, self.cache_path)

    async def read_lkg_cache(self) -> LKGCache | None:
        """Read and verify last-known-good cache.

        Returns:
            LKGCache if valid, None if missing or tampered

        Note:
            This method verifies HMAC signature and returns None if tampered.
        """
        if not self.cache_path.exists():
            return None

        try:
            # Read cache file
            cache_bytes = await asyncio.to_thread(self.cache_path.read_bytes)
            signed_cache = orjson.loads(cache_bytes)

            # Verify HMAC signature
            payload = await verify_cache_async(signed_cache, self.hmac_key_base64)
            if payload is None:
                # Tampered cache
                return None

            # Construct LKGCache model
            return LKGCache(
                payload=payload["payload"],
                config_epoch=payload["config_epoch"],
                generated_at=datetime.fromisoformat(payload["generated_at"]),
                signature=signed_cache["signature"],
                algorithm=signed_cache.get("algorithm", "hmac-sha256"),
            )

        except (OSError, ValueError, KeyError, TypeError) as e:
            # Cache file corrupted or invalid format
            return None

    async def verify_lkg_signature(self) -> bool:
        """Verify LKG cache signature without loading full payload.

        Returns:
            True if signature is valid, False otherwise
        """
        cache = await self.read_lkg_cache()
        return cache is not None

    async def atomic_update_from_db(
        self,
        service_configs: dict[str, dict[str, Any]],
        config_epoch: str,
        timeout_ms: int = 100,
    ) -> bool:
        """Update cache atomically within timeout after successful DB read.

        Args:
            service_configs: Service configurations from database
            config_epoch: Current database epoch
            timeout_ms: Maximum time to complete update (default 100ms)

        Returns:
            True if update completed within timeout, False if timed out
        """
        try:
            await asyncio.wait_for(
                self.write_lkg_cache(service_configs, config_epoch),
                timeout=timeout_ms / 1000.0,
            )
            return True
        except asyncio.TimeoutError:
            return False

    async def get_cached_config(self, service: str) -> dict[str, Any] | None:
        """Get cached configuration for a specific service.

        Args:
            service: Service name

        Returns:
            Service configuration if cached and valid, None otherwise
        """
        cache = await self.read_lkg_cache()
        if cache is None:
            return None

        return cache.payload.get(service)

    async def get_all_cached_configs(self) -> dict[str, dict[str, Any]] | None:
        """Get all cached service configurations.

        Returns:
            All service configs if cache valid, None if missing or tampered
        """
        cache = await self.read_lkg_cache()
        if cache is None:
            return None

        return cache.payload

    async def delete_cache(self) -> None:
        """Delete cache file (for testing or manual recovery)."""
        if self.cache_path.exists():
            await asyncio.to_thread(self.cache_path.unlink)
