#!/usr/bin/env python3
"""
Convert ONNX embedding model to RKNN format for NPU acceleration.

This script converts ONNX embedding models (like BERT-based SentenceTransformers)
to RKNN format optimized for the RK3588 NPU.

Usage:
    python convert_onnx_to_rknn.py input.onnx output.rknn [--quantize]
    
Examples:
    # Basic conversion
    python convert_onnx_to_rknn.py /tmp/embedder.onnx /models/embedder/embedder.rknn
    
    # With quantization for better NPU performance
    python convert_onnx_to_rknn.py /tmp/embedder.onnx /models/embedder/embedder.rknn --quantize
"""

from __future__ import annotations

import argparse
import logging
import platform
import sys
from pathlib import Path
from typing import List, Optional

import numpy as np

try:
    from rknn.api import RKNN
except ImportError:
    print("ERROR: rknn-toolkit2 is required but not installed.", file=sys.stderr)
    print("Install it with: pip install rknn-toolkit2", file=sys.stderr)
    sys.exit(1)

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)


def create_calibration_dataset(
    num_samples: int = 100,
    seq_length: int = 256,
    vocab_size: int = 30522,  # BERT base vocab size
) -> List[List[np.ndarray]]:
    """Create calibration dataset for quantization.
    
    Args:
        num_samples: Number of calibration samples to generate
        seq_length: Sequence length for tokenized input
        vocab_size: Vocabulary size (30522 for BERT)
        
    Returns:
        List of input sets, where each set is [input_ids, attention_mask, (token_type_ids)]
    """
    logger.info(f"Creating {num_samples} calibration samples")
    logger.info(f"  Sequence length: {seq_length}")
    logger.info(f"  Vocab size: {vocab_size}")
    
    dataset = []
    
    for i in range(num_samples):
        # Generate realistic tokenized text
        # Most tokens should be valid vocab IDs, with some special tokens
        
        # Vary sequence lengths (20-256)
        actual_length = np.random.randint(20, seq_length + 1)
        
        # Generate input_ids
        input_ids = np.zeros(seq_length, dtype=np.int64)
        input_ids[0] = 101  # [CLS] token
        
        # Fill with random vocab IDs (avoid special tokens 0-999)
        input_ids[1:actual_length-1] = np.random.randint(1000, vocab_size, size=actual_length-2)
        
        input_ids[actual_length-1] = 102  # [SEP] token
        # Rest are [PAD] = 0
        
        # Generate attention_mask (1 for real tokens, 0 for padding)
        attention_mask = np.zeros(seq_length, dtype=np.int64)
        attention_mask[:actual_length] = 1
        
        # Token type ids (all zeros for single sentence)
        token_type_ids = np.zeros(seq_length, dtype=np.int64)
        
        # RKNN expects inputs as list: [input_ids, attention_mask, token_type_ids]
        # Each with shape (1, seq_length) for batch size 1
        dataset.append([
            input_ids.reshape(1, -1).astype(np.int64),
            attention_mask.reshape(1, -1).astype(np.int64),
            token_type_ids.reshape(1, -1).astype(np.int64),
        ])
    
    logger.info(f"Created {len(dataset)} calibration samples")
    return dataset


def convert_onnx_to_rknn(
    onnx_path: Path,
    rknn_path: Path,
    *,
    quantize: bool = False,
    target_platform: str = "rk3588",
    optimization_level: int = 3,
) -> bool:
    """Convert ONNX embedding model to RKNN format.
    
    Args:
        onnx_path: Path to input ONNX model
        rknn_path: Path for output .rknn model
        quantize: Enable quantization (w8a8) for better NPU performance
        target_platform: Target Rockchip platform (rk3588, rk3566, etc.)
        optimization_level: RKNN optimization level (0-3, higher = more aggressive)
        
    Returns:
        True if conversion successful, False otherwise
        
    Note:
        - quantize=True uses w8a8 (8-bit weights/activations) for maximum NPU efficiency
        - quantize=False uses w16a16i (16-bit) for higher precision but slower inference
        - For embeddings, w8a8 typically provides good performance with minimal accuracy loss
    """
    if not onnx_path.exists():
        logger.error(f"ONNX model not found: {onnx_path}")
        return False
    
    # Check platform
    arch = platform.machine().lower()
    logger.info(f"Converting {onnx_path} to {rknn_path}")
    logger.info(f"Target platform: {target_platform}")
    logger.info(f"Architecture: {arch}")
    logger.info(f"Quantization: {'enabled (w8a8)' if quantize else 'disabled (w16a16i)'}")
    logger.info(f"Optimization level: {optimization_level}")
    
    rknn = RKNN(verbose=True)
    
    try:
        # Configure RKNN
        logger.info("Configuring RKNN...")
        
        # For BERT embeddings, no normalization needed (tokenized integers)
        # Mean/std only apply to float inputs
        if quantize:
            ret = rknn.config(
                target_platform=target_platform,
                optimization_level=optimization_level,
                quantized_dtype="asymmetric_quantized-8",  # w8a8
                quantized_algorithm="normal",
            )
        else:
            ret = rknn.config(
                target_platform=target_platform,
                optimization_level=optimization_level,
            )
        
        if ret != 0:
            logger.error("RKNN config failed")
            return False
        
        # Load ONNX model with fixed input shapes
        # RKNN doesn't support dynamic shapes well, so we fix to batch=1, seq_len=256
        logger.info("Loading ONNX model...")
        logger.info("Using fixed input shapes: batch_size=1, sequence_length=256")
        
        # Specify input shapes explicitly (RKNN requirement)
        input_size_list = [
            [1, 256],  # input_ids: [batch, seq_len]
            [1, 256],  # attention_mask: [batch, seq_len]
            [1, 256],  # token_type_ids: [batch, seq_len]
        ]
        
        ret = rknn.load_onnx(
            model=str(onnx_path),
            input_size_list=input_size_list
        )
        
        if ret != 0:
            logger.error("Failed to load ONNX model")
            return False
        
        # Build RKNN model
        logger.info("Building RKNN model...")
        
        if quantize:
            # For BERT models, RKNN quantization can be tricky with integer inputs
            # Try building without explicit calibration dataset first
            # RKNN will use default quantization for the model
            logger.info("Using automatic quantization (no calibration dataset for integer inputs)")
            ret = rknn.build(do_quantization=True)
        else:
            ret = rknn.build(do_quantization=False)
        
        if ret != 0:
            logger.error("RKNN build failed")
            return False
        
        # Export RKNN model
        logger.info(f"Exporting RKNN model to {rknn_path}...")
        rknn_path.parent.mkdir(parents=True, exist_ok=True)
        ret = rknn.export_rknn(str(rknn_path))
        
        if ret != 0:
            logger.error("RKNN export failed")
            return False
        
        logger.info("✅ Conversion completed successfully!")
        logger.info("")
        logger.info("Model location:")
        logger.info(f"  {rknn_path}")
        logger.info("")
        logger.info("Next steps:")
        logger.info("1. Enable in .env:")
        logger.info("     NPU_EMBEDDER_ENABLED=1")
        logger.info(f"     RKNN_EMBEDDER_PATH=/data/model_cache/embedder/{rknn_path.name}")
        logger.info("2. Restart memory worker: docker compose restart memory")
        logger.info("3. Check logs for 'Using NPU embedder' message")
        
        return True
        
    except Exception as e:
        logger.error(f"Conversion failed with exception: {e}", exc_info=True)
        return False
    finally:
        # Always release RKNN resources
        rknn.release()


def validate_rknn_model(rknn_path: Path) -> bool:
    """Validate the converted RKNN model by running a test inference.
    
    Args:
        rknn_path: Path to the .rknn model to validate
        
    Returns:
        True if validation successful, False otherwise
    """
    logger.info(f"Validating RKNN model: {rknn_path}")
    
    try:
        from rknnlite.api import RKNNLite
    except ImportError:
        logger.warning("rknn-toolkit-lite2 not available, skipping validation")
        logger.info("Validation should be run on the target NPU device")
        return True
    
    rknn_lite = RKNNLite()
    
    try:
        # Load model
        ret = rknn_lite.load_rknn(str(rknn_path))
        if ret != 0:
            logger.error("Failed to load RKNN model for validation")
            return False
        
        # Initialize runtime
        ret = rknn_lite.init_runtime(core_mask=RKNNLite.NPU_CORE_AUTO)
        if ret != 0:
            logger.error("Failed to initialize RKNN runtime")
            return False
        
        # Test inference with dummy tokenized input
        seq_length = 256
        dummy_inputs = [
            np.random.randint(0, 30522, (1, seq_length), dtype=np.int64),  # input_ids
            np.ones((1, seq_length), dtype=np.int64),  # attention_mask
            np.zeros((1, seq_length), dtype=np.int64),  # token_type_ids
        ]
        
        outputs = rknn_lite.inference(inputs=dummy_inputs)
        
        if outputs and len(outputs) > 0:
            output_shape = outputs[0].shape
            logger.info(f"✅ Validation successful!")
            logger.info(f"   Output shape: {output_shape}")
            logger.info(f"   Expected: (1, {seq_length}, 384) for BERT embeddings")
            return True
        else:
            logger.error("No outputs received from inference")
            return False
        
    except Exception as e:
        logger.error(f"Validation failed: {e}", exc_info=True)
        return False
    finally:
        rknn_lite.release()


def main() -> int:
    """Main entry point for the conversion script."""
    parser = argparse.ArgumentParser(
        description="Convert ONNX embedding model to RKNN format for NPU acceleration",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    
    parser.add_argument("input", type=Path, help="Input ONNX model file")
    parser.add_argument("output", type=Path, help="Output .rknn model file")
    parser.add_argument(
        "--quantize",
        action="store_true",
        help="Enable w8a8 quantization for maximum NPU performance"
    )
    parser.add_argument(
        "--target",
        default="rk3588",
        choices=["rk3588", "rk3566", "rk3568"],
        help="Target Rockchip platform (default: rk3588)"
    )
    parser.add_argument(
        "--optimization-level",
        type=int,
        default=3,
        choices=[0, 1, 2, 3],
        help="RKNN optimization level (default: 3)"
    )
    parser.add_argument(
        "--validate",
        action="store_true",
        help="Validate the converted model with test inference (requires NPU device)"
    )
    parser.add_argument(
        "--verbose",
        action="store_true",
        help="Enable verbose logging"
    )
    
    args = parser.parse_args()
    
    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)
    
    # Validate inputs
    if not args.input.exists():
        logger.error(f"Input file does not exist: {args.input}")
        return 1
    
    if args.input.suffix.lower() != ".onnx":
        logger.error(f"Input file must be .onnx, got: {args.input.suffix}")
        return 1
    
    if args.output.suffix.lower() != ".rknn":
        logger.error(f"Output file must have .rknn extension, got: {args.output.suffix}")
        return 1
    
    # Convert model
    success = convert_onnx_to_rknn(
        args.input,
        args.output,
        quantize=args.quantize,
        target_platform=args.target,
        optimization_level=args.optimization_level,
    )
    
    if not success:
        logger.error("❌ Conversion failed")
        return 1
    
    # Validate if requested
    if args.validate:
        if not validate_rknn_model(args.output):
            logger.warning("⚠️  Validation failed or skipped")
            logger.info("   Run validation on the target NPU device")
    
    logger.info("🎉 Conversion completed successfully!")
    return 0


if __name__ == "__main__":
    sys.exit(main())
