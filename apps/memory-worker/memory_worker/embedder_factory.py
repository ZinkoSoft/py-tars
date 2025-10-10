"""Factory for creating embedders with automatic CPU/NPU detection."""

from __future__ import annotations

import logging
import os
from typing import Union

logger = logging.getLogger(__name__)


def create_embedder(
    model_name: str,
) -> Union["STEmbedder", "NPUEmbedder"]:  # type: ignore[name-defined]
    """Create embedder with automatic NPU detection and CPU fallback.
    
    Selection logic:
        1. If NPU_EMBEDDER_ENABLED=1 and NPU available → NPUEmbedder
        2. Otherwise → STEmbedder (CPU)
    
    Args:
        model_name: HuggingFace model name (e.g., "sentence-transformers/all-MiniLM-L6-v2")
    
    Returns:
        NPUEmbedder if NPU available and enabled, otherwise STEmbedder
    """
    from .service import STEmbedder  # Import here to avoid circular dependency
    
    # Check if NPU is enabled via environment
    npu_enabled = os.getenv("NPU_EMBEDDER_ENABLED", "0") == "1"
    
    if not npu_enabled:
        logger.info("NPU embedder disabled (NPU_EMBEDDER_ENABLED=0), using CPU embedder")
        return STEmbedder(model_name)
    
    # NPU is enabled, try to create NPU embedder
    logger.info("NPU embedder enabled, attempting to initialize NPU...")
    
    try:
        from .npu_embedder import create_npu_embedder
        
        npu_embedder = create_npu_embedder(base_model=model_name)
        
        if npu_embedder is not None:
            logger.info("✓ Using NPU embedder for %s", model_name)
            return npu_embedder
        else:
            logger.warning(
                "NPU embedder creation failed (device or model not available), "
                "falling back to CPU embedder"
            )
    except ImportError as e:
        logger.warning(
            "Failed to import NPU embedder (missing dependencies: %s), "
            "falling back to CPU embedder",
            e
        )
    except Exception as e:
        logger.error(
            "Unexpected error creating NPU embedder: %s, "
            "falling back to CPU embedder",
            e,
            exc_info=True
        )
    
    # Fallback to CPU
    fallback_enabled = os.getenv("NPU_FALLBACK_CPU", "1") == "1"
    if fallback_enabled:
        logger.info("✓ Using CPU embedder (fallback) for %s", model_name)
        return STEmbedder(model_name)
    else:
        raise RuntimeError(
            "NPU embedder unavailable and CPU fallback disabled (NPU_FALLBACK_CPU=0). "
            "Enable CPU fallback or fix NPU configuration."
        )
