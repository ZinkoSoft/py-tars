"""Adapter to bridge tars.config.ConfigLibrary with the stt-worker runtime.

This module initializes ConfigLibrary, loads STTWorkerConfig at startup,
applies values into the existing `stt_worker.config` module (so other modules
that import constants continue to work), and subscribes to runtime updates.
"""
from __future__ import annotations

import asyncio
import logging
from typing import Callable

from tars.config.library import ConfigLibrary
from tars.config.models import STTWorkerConfig

logger = logging.getLogger(__name__)

# Internal runtime state
_config_lib: ConfigLibrary | None = None
_external_callbacks: list[Callable[[STTWorkerConfig], None]] = []


async def initialize_and_subscribe(mqtt_url: str | None = None) -> None:
    """Initialize the ConfigLibrary and subscribe to updates for stt-worker.

    This will load the initial configuration and apply it into
    `stt_worker.config` module namespace.
    """
    global _config_lib

    if _config_lib is not None:
        return

    _config_lib = ConfigLibrary(service_name="stt-worker", mqtt_url=mqtt_url)
    await _config_lib.initialize()

    # Load initial config and apply
    try:
        stt_config = await _config_lib.get_config(STTWorkerConfig)
        _apply_to_module(stt_config)
    except Exception as e:
        logger.warning("Failed to load initial STT config: %s", e)

    # Subscribe to updates if possible
    try:
        await _config_lib.subscribe_updates(_on_update_message, STTWorkerConfig)
    except Exception as e:
        logger.warning("Failed to subscribe to config updates: %s", e)


def _apply_to_module(cfg: STTWorkerConfig) -> None:
    """Apply configuration values to stt_worker.config module attributes.

    Only a subset of fields are mapped here; they mirror the constants used
    throughout the stt-worker codebase. This keeps existing modules working
    while enabling runtime updates.
    """
    try:
        from . import config as cfg_mod

        # Map Pydantic fields to module-level names
        mapping = {
            "whisper_model": "WHISPER_MODEL",
            "stt_backend": "STT_BACKEND",
            "ws_url": "WS_URL",
            "streaming_partials": "STREAMING_PARTIALS",
            "vad_threshold": "VAD_ENHANCED_ANALYSIS",  # approximate mapping
            "vad_speech_pad_ms": "PARTIAL_INTERVAL_MS",
            "vad_silence_duration_ms": "PARTIAL_MIN_DURATION_MS",
            "sample_rate": "SAMPLE_RATE",
            "channels": "CHANNELS",
        }

        for field_name, module_name in mapping.items():
            if hasattr(cfg, field_name):
                value = getattr(cfg, field_name)
                # Defensive: only set attribute if exists on module
                if hasattr(cfg_mod, module_name):
                    setattr(cfg_mod, module_name, value)
                    logger.info("Applied config %s=%s", module_name, value)
    except Exception as e:
        logger.exception("Error applying config to module: %s", e)


def _on_update_message(new_cfg_model) -> None:
    """Internal callback invoked by ConfigLibrary when an update arrives.

    This function applies the new configuration and notifies external
    callbacks (such as the running service instance) so they can adjust
    runtime behavior.
    """
    try:
        # Apply module-level overrides
        _apply_to_module(new_cfg_model)

        # Notify external listeners
        for cb in list(_external_callbacks):
            try:
                cb(new_cfg_model)
            except Exception:
                logger.exception("External callback failed")
    except Exception:
        logger.exception("Failed to handle config update")


def register_callback(cb: Callable[[STTWorkerConfig], None]) -> None:
    """Register an external synchronous callback to be invoked on updates.

    Callbacks are invoked with the Pydantic model instance.
    """
    _external_callbacks.append(cb)


async def close() -> None:
    """Close the underlying ConfigLibrary (cleanup)."""
    global _config_lib
    if _config_lib is not None:
        try:
            await _config_lib.close()
        except Exception:
            logger.exception("Error closing ConfigLibrary")
        _config_lib = None
