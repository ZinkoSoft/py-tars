"""Adapter to bridge tars.config.ConfigLibrary with the tts-worker runtime.

This module initializes ConfigLibrary, loads TTSWorkerConfig at startup,
applies values into the existing `tts_worker.config` module (so other modules
that import constants continue to work), and subscribes to runtime updates.
"""
from __future__ import annotations

import logging
from typing import Callable

from tars.config.library import ConfigLibrary
from tars.config.models import TTSWorkerConfig

logger = logging.getLogger(__name__)

# Internal runtime state
_config_lib: ConfigLibrary | None = None
_external_callbacks: list[Callable[[TTSWorkerConfig], None]] = []


async def initialize_and_subscribe(mqtt_url: str | None = None) -> None:
    """Initialize the ConfigLibrary and subscribe to updates for tts-worker.

    This will load the initial configuration and apply it into
    `tts_worker.config` module namespace.
    """
    global _config_lib

    if _config_lib is not None:
        return

    _config_lib = ConfigLibrary(service_name="tts-worker", mqtt_url=mqtt_url)
    await _config_lib.initialize()

    # Load initial config and apply
    try:
        tts_config = await _config_lib.get_config(TTSWorkerConfig)
        _apply_to_module(tts_config)
    except Exception as e:
        logger.warning("Failed to load initial TTS config: %s", e)

    # Subscribe to updates if possible
    try:
        await _config_lib.subscribe_updates(_on_update_message, TTSWorkerConfig)
    except Exception as e:
        logger.warning("Failed to subscribe to config updates: %s", e)


def _apply_to_module(cfg: TTSWorkerConfig) -> None:
    """Apply configuration values to tts_worker.config module attributes.

    Maps Pydantic fields to module-level constants used throughout
    the tts-worker codebase. This keeps existing modules working
    while enabling runtime updates.
    """
    try:
        from . import config as cfg_mod

        # Map Pydantic fields to module-level names
        mapping = {
            "piper_voice": "PIPER_VOICE",
            "tts_provider": "TTS_PROVIDER",
            "tts_streaming": "TTS_STREAMING",
            "tts_pipeline": "TTS_PIPELINE",
            "tts_simpleaudio": "TTS_SIMPLEAUDIO",
            "tts_concurrency": "TTS_CONCURRENCY",
            "tts_aggregate": "TTS_AGGREGATE",
            "tts_aggregate_debounce_ms": "TTS_AGGREGATE_DEBOUNCE_MS",
            "tts_aggregate_single_wav": "TTS_AGGREGATE_SINGLE_WAV",
            "tts_wake_cache_enable": "TTS_WAKE_CACHE_ENABLE",
            "tts_wake_cache_dir": "TTS_WAKE_CACHE_DIR",
            "tts_wake_cache_max": "TTS_WAKE_CACHE_MAX",
            "eleven_api_base": "ELEVEN_API_BASE",
            "eleven_api_key": "ELEVEN_API_KEY",
            "eleven_voice_id": "ELEVEN_VOICE_ID",
            "eleven_model_id": "ELEVEN_MODEL_ID",
            "eleven_optimize_streaming": "ELEVEN_OPTIMIZE_STREAMING",
        }

        for field_name, module_name in mapping.items():
            if hasattr(cfg, field_name):
                value = getattr(cfg, field_name)
                # Convert bool to int for legacy compatibility (TTS_STREAMING, etc.)
                if isinstance(value, bool) and module_name in [
                    "TTS_STREAMING",
                    "TTS_PIPELINE",
                    "TTS_SIMPLEAUDIO",
                    "TTS_AGGREGATE",
                    "TTS_AGGREGATE_SINGLE_WAV",
                    "TTS_WAKE_CACHE_ENABLE",
                ]:
                    value = int(value)
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


def register_callback(cb: Callable[[TTSWorkerConfig], None]) -> None:
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
