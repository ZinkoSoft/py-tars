"""NPU-accelerated embedder using RKNN Lite2 for RK3588."""

from __future__ import annotations

import asyncio
import logging
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Optional

import numpy as np
from transformers import AutoTokenizer

logger = logging.getLogger(__name__)

try:
    from rknnlite.api import RKNNLite
except ImportError:
    RKNNLite = None  # type: ignore[assignment,misc]


class NPUEmbedder:
    """SentenceTransformer embedding using RKNN NPU acceleration.
    
    This class provides the same interface as STEmbedder but uses the NPU
    for BERT inference while keeping tokenization and pooling on CPU.
    
    Architecture:
        Text → Tokenization (CPU) → BERT (NPU) → Pooling (CPU) → Embedding
    
    The RKNN model expects fixed-shape inputs [1, 256]:
        - input_ids: Token IDs
        - attention_mask: Mask for real tokens
        - token_type_ids: All zeros for single sentence
    
    Args:
        rknn_model_path: Path to .rknn model file
        base_model: HuggingFace model name for tokenizer
        max_seq_length: Maximum sequence length (must match RKNN model)
        npu_core_mask: NPU core selection (0=auto, 1=core0, 2=core1, 4=core2, 7=all)
    """

    def __init__(
        self,
        rknn_model_path: str,
        base_model: str = "sentence-transformers/all-MiniLM-L6-v2",
        max_seq_length: int = 256,
        npu_core_mask: int = 0,
    ):
        if RKNNLite is None:
            raise ImportError(
                "rknn-toolkit-lite2 is not installed. "
                "Install it to enable NPU embedder: pip install rknn-toolkit-lite2"
            )
        
        self.rknn_model_path = rknn_model_path
        self.base_model = base_model
        self.max_seq_length = max_seq_length
        self.npu_core_mask = npu_core_mask
        
        # Verify RKNN model exists
        if not Path(rknn_model_path).exists():
            raise FileNotFoundError(
                f"RKNN model not found: {rknn_model_path}\n"
                f"Models should be automatically converted at container startup."
            )
        
        # Initialize tokenizer (CPU)
        logger.info("Loading tokenizer: %s", base_model)
        self.tokenizer = AutoTokenizer.from_pretrained(base_model)
        
        # Initialize RKNN runtime (NPU)
        logger.info("Loading RKNN model: %s", rknn_model_path)
        self._rknn = RKNNLite()
        
        ret = self._rknn.load_rknn(rknn_model_path)
        if ret != 0:
            raise RuntimeError(f"Failed to load RKNN model: {rknn_model_path} (error code: {ret})")
        
        ret = self._rknn.init_runtime(core_mask=npu_core_mask)
        if ret != 0:
            self._rknn.release()
            raise RuntimeError(
                f"Failed to initialize RKNN runtime with core mask {npu_core_mask} (error code: {ret})"
            )
        
        logger.info(
            "✓ NPU embedder ready: model=%s, max_seq_length=%d, npu_core_mask=%d",
            Path(rknn_model_path).name,
            max_seq_length,
            npu_core_mask,
        )
        
        # Thread pool for async operations
        self._executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix="npu-embed")
    
    def __call__(self, texts: list[str]) -> np.ndarray:
        """Synchronous embedding (blocks for computation).
        
        For async contexts, prefer embed_async() to avoid blocking the event loop.
        """
        return self._encode_sync(texts)
    
    def _encode_sync(self, texts: list[str]) -> np.ndarray:
        """Internal sync implementation of encoding."""
        if not texts:
            return np.array([], dtype=np.float32).reshape(0, 384)
        
        embeddings = []
        for text in texts:
            embedding = self._encode_single(text)
            embeddings.append(embedding)
        
        return np.array(embeddings, dtype=np.float32)
    
    def _encode_single(self, text: str) -> np.ndarray:
        """Encode a single text string to embedding vector.
        
        Pipeline:
            1. Tokenize text (CPU)
            2. Run BERT encoder on NPU
            3. Mean pooling over token embeddings (CPU)
            4. L2 normalization (CPU)
        
        Returns:
            384-dimensional normalized embedding vector
        """
        # Step 1: Tokenization (CPU)
        encoded = self.tokenizer(
            text,
            padding="max_length",
            truncation=True,
            max_length=self.max_seq_length,
            return_tensors="np",
        )
        
        input_ids = encoded["input_ids"].astype(np.int64)  # [1, 256]
        attention_mask = encoded["attention_mask"].astype(np.int64)  # [1, 256]
        token_type_ids = np.zeros_like(input_ids, dtype=np.int64)  # [1, 256]
        
        # Step 2: BERT inference on NPU
        # Note: RKNN model may only accept input_ids and attention_mask
        # Try with all 3 inputs first, fall back to 2 if needed
        try:
            outputs = self._rknn.inference(
                inputs=[input_ids, attention_mask]
            )
            
            if not outputs or len(outputs) == 0:
                logger.warning("NPU inference returned no outputs, falling back to zeros")
                return np.zeros(384, dtype=np.float32)
            
            # Output shape: [1, max_seq_length, hidden_dim] = [1, 256, 384]
            token_embeddings = outputs[0].astype(np.float32)  # FP16 → FP32
            
        except Exception as e:
            logger.error("NPU inference failed: %s", e)
            raise RuntimeError(f"NPU inference error: {e}")
        
        # Step 3: Mean pooling (CPU)
        # Average token embeddings, respecting attention mask
        attention_mask_expanded = np.expand_dims(attention_mask, axis=-1)  # [1, 256, 1]
        attention_mask_expanded = attention_mask_expanded.astype(np.float32)
        
        # Mask out padding tokens
        masked_embeddings = token_embeddings * attention_mask_expanded  # [1, 256, 384]
        
        # Sum over sequence dimension
        sum_embeddings = np.sum(masked_embeddings, axis=1)  # [1, 384]
        
        # Count real tokens
        sum_mask = np.maximum(np.sum(attention_mask_expanded, axis=1), 1e-9)  # [1, 1]
        
        # Average
        mean_embeddings = sum_embeddings / sum_mask  # [1, 384]
        
        # Step 4: L2 normalization (CPU)
        sentence_embedding = mean_embeddings[0]  # [384]
        norm = np.linalg.norm(sentence_embedding)
        if norm > 0:
            sentence_embedding = sentence_embedding / norm
        
        return sentence_embedding  # [384]
    
    async def embed_async(self, texts: list[str]) -> np.ndarray:
        """Async wrapper for embedding using thread pool.
        
        Offloads NPU inference to avoid blocking the event loop during
        MQTT message processing.
        
        Args:
            texts: List of text strings to embed
            
        Returns:
            numpy array of embeddings (normalized float32)
        """
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(self._executor, self._encode_sync, texts)
    
    def __del__(self):
        """Release RKNN runtime resources."""
        if hasattr(self, "_rknn"):
            try:
                self._rknn.release()
            except Exception:
                pass  # Ignore cleanup errors
        
        if hasattr(self, "_executor"):
            try:
                self._executor.shutdown(wait=False)
            except Exception:
                pass


def create_npu_embedder(
    rknn_model_path: Optional[str] = None,
    base_model: str = "sentence-transformers/all-MiniLM-L6-v2",
    npu_core_mask: Optional[int] = None,
) -> Optional[NPUEmbedder]:
    """Create NPU embedder with automatic configuration from environment.
    
    Args:
        rknn_model_path: Override RKNN_EMBEDDER_PATH env var
        base_model: Override EMBED_MODEL env var
        npu_core_mask: Override NPU_CORE_MASK env var
    
    Returns:
        NPUEmbedder instance or None if NPU unavailable
    """
    import os
    
    if RKNNLite is None:
        logger.info("rknn-toolkit-lite2 not installed, NPU embedder unavailable")
        return None
    
    # Get configuration from environment
    if rknn_model_path is None:
        rknn_model_path = os.getenv("RKNN_EMBEDDER_PATH")
    
    if not rknn_model_path:
        logger.info("RKNN_EMBEDDER_PATH not set, NPU embedder unavailable")
        return None
    
    if not Path(rknn_model_path).exists():
        logger.warning(
            "RKNN model not found: %s\n"
            "NPU embedder unavailable, will use CPU fallback",
            rknn_model_path
        )
        return None
    
    if npu_core_mask is None:
        npu_core_mask = int(os.getenv("NPU_CORE_MASK", "0"))
    
    # Check for NPU device
    npu_device = Path("/dev/dri/renderD129")
    if not npu_device.exists():
        logger.warning(
            "NPU device not found: %s\n"
            "NPU embedder unavailable, will use CPU fallback",
            npu_device
        )
        return None
    
    try:
        embedder = NPUEmbedder(
            rknn_model_path=rknn_model_path,
            base_model=base_model,
            npu_core_mask=npu_core_mask,
        )
        return embedder
    except Exception as e:
        logger.error("Failed to create NPU embedder: %s", e)
        return None
